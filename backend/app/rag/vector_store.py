"""Qdrant, the vector database: one point per table, for every user, in one collection.

A Qdrant *point* = id + named vectors + payload (JSON metadata):
    id       the table's UUID (stable: re-indexing a table overwrites its point)
    vectors  "dense": 384 floats (cosine similarity) + "bm25": sparse keyword weights
    payload  user_id, schema_id, table names, the indexed document, foreign keys...

Multi-tenancy: all users share ONE collection, and every search is filtered by
user_id + schema_id. (One collection per user would mean thousands of collections,
each with its own index overhead; Qdrant's recommended design is a payload filter
with a "tenant" index, which also keeps each tenant's points together on disk.)

The client runs either against a Qdrant server (QDRANT_URL) or embedded in this
process (QDRANT_PATH). Embedded mode searches by brute force (exact, fine for
thousands of points) and ignores payload indexes; a server uses HNSW graphs.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, TypeVar

import httpx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.rag.embeddings import Embedding, SparseVector, get_embedder

logger = logging.getLogger(__name__)

T = TypeVar("T")
# Transport failures (connection reset, timeout): worth one retry. HTTP errors with a
# status code (bad request, auth) are not, they would fail the same way again.
NETWORK_ERRORS = (ResponseHandlingException, httpx.TransportError, TimeoutError)

DENSE = "dense"  # vector names inside each point
SPARSE = "bm25"
SearchMode = Literal["dense", "sparse"]


@dataclass(frozen=True)
class TablePoint:
    table_id: uuid.UUID
    embedding: Embedding
    payload: dict[str, Any]


@dataclass(frozen=True)
class SearchHit:
    table_id: uuid.UUID
    score: float
    payload: dict[str, Any]


def _sparse(vector: SparseVector) -> models.SparseVector:
    return models.SparseVector(indices=vector.indices, values=vector.values)


def _keyword(key: str, value: str) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


class SchemaIndex:
    """Our only door to Qdrant: everything is scoped to a user and a schema."""

    def __init__(self, client: AsyncQdrantClient, collection: str, dense_dim: int, *, local: bool):
        self.client = client
        self.collection = collection
        self.dense_dim = dense_dim
        self.local = local
        self._ready = False

    async def ensure_collection(self) -> None:
        """Create the collection (and its payload indexes) once; check it on later runs."""
        if self._ready:
            return
        try:
            if await self.client.collection_exists(self.collection):
                info = await self.client.get_collection(self.collection)
                size = info.config.params.vectors[DENSE].size  # type: ignore[index]
                if size != self.dense_dim:
                    raise VectorStoreError(
                        f"Collection '{self.collection}' stores {size}-d vectors but the "
                        f"embedding model makes {self.dense_dim}-d ones. Set QDRANT_COLLECTION "
                        "to a new name (or delete the old collection), then rebuild the indexes."
                    )
            else:
                await self.client.create_collection(
                    self.collection,
                    vectors_config={
                        DENSE: models.VectorParams(
                            size=self.dense_dim, distance=models.Distance.COSINE
                        )
                    },
                    # IDF ("how rare is this word?") is computed by Qdrant over the whole
                    # collection at search time, so adding documents never stales old vectors.
                    sparse_vectors_config={
                        SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
                    },
                )
                if not self.local:  # embedded mode ignores payload indexes
                    await self.client.create_payload_index(
                        self.collection,
                        "user_id",
                        field_schema=models.KeywordIndexParams(type="keyword", is_tenant=True),
                    )
                    await self.client.create_payload_index(self.collection, "schema_id", "keyword")
                logger.info(
                    "Created Qdrant collection '%s' (%s-d dense + BM25)",
                    self.collection,
                    self.dense_dim,
                )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise _unavailable(exc) from exc
        self._ready = True

    async def ping(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False

    async def upsert(self, points: list[TablePoint]) -> None:
        if not points:
            return
        await self.ensure_collection()
        structs = [
            models.PointStruct(
                id=str(p.table_id),
                vector={DENSE: p.embedding.dense, SPARSE: _sparse(p.embedding.sparse)},
                payload=p.payload,
            )
            for p in points
        ]
        await self._call(lambda: self.client.upsert(self.collection, points=structs, wait=True))

    async def delete_missing(self, schema_id: uuid.UUID, keep: list[uuid.UUID]) -> None:
        """Remove the schema's points whose table no longer exists."""
        await self._delete(
            models.Filter(
                must=[_keyword("schema_id", str(schema_id))],
                must_not=[models.HasIdCondition(has_id=[str(t) for t in keep])] if keep else None,
            )
        )

    async def delete_schema(self, schema_id: uuid.UUID) -> None:
        await self._delete(models.Filter(must=[_keyword("schema_id", str(schema_id))]))

    async def delete_user(self, user_id: uuid.UUID) -> None:
        await self._delete(models.Filter(must=[_keyword("user_id", str(user_id))]))

    async def count(self, schema_id: uuid.UUID) -> int:
        await self.ensure_collection()
        result = await self._call(
            lambda: self.client.count(
                self.collection,
                count_filter=models.Filter(must=[_keyword("schema_id", str(schema_id))]),
                exact=True,
            )
        )
        return result.count

    async def search(
        self,
        *,
        user_id: uuid.UUID,
        schema_id: uuid.UUID,
        mode: SearchMode,
        query: Embedding,
        limit: int,
    ) -> list[SearchHit]:
        await self.ensure_collection()
        # The tenant filter is applied INSIDE the vector search, not afterwards: another
        # user's tables can never come back, and the limit counts only allowed points.
        tenant = models.Filter(
            must=[_keyword("user_id", str(user_id)), _keyword("schema_id", str(schema_id))]
        )
        vector = query.dense if mode == "dense" else _sparse(query.sparse)
        result = await self._call(
            lambda: self.client.query_points(
                self.collection,
                query=vector,
                using=DENSE if mode == "dense" else SPARSE,
                query_filter=tenant,
                limit=limit,
                with_payload=True,
            )
        )
        return [
            SearchHit(table_id=uuid.UUID(str(p.id)), score=p.score, payload=p.payload or {})
            for p in result.points
        ]

    async def close(self) -> None:
        await self.client.close()

    async def _delete(self, selector: models.Filter) -> None:
        await self.ensure_collection()
        await self._call(
            lambda: self.client.delete(
                self.collection, points_selector=models.FilterSelector(filter=selector), wait=True
            )
        )

    async def _call(self, make: Callable[[], Awaitable[T]]) -> T:
        """Run one Qdrant request; retry once if the network failed.

        Every request we send is safe to repeat (searches read; upserts overwrite the
        same point ids; deletes are by filter), so one quick retry hides most blips
        between us and a hosted cluster without risking duplicates.
        """
        for attempt in (1, 2):
            try:
                return await make()
            except NETWORK_ERRORS as exc:
                if attempt == 2:
                    raise _unavailable(exc) from exc
                logger.info("Qdrant request failed (%r), retrying once", exc)
                await asyncio.sleep(0.3)
            except Exception as exc:
                raise _unavailable(exc) from exc
        raise AssertionError("unreachable")


def _unavailable(exc: Exception) -> VectorStoreError:
    # repr(): some network errors have an empty message (e.g. a timeout).
    logger.warning("Qdrant call failed: %r", exc)
    where = settings.qdrant_url or f"embedded storage '{settings.qdrant_path}'"
    return VectorStoreError(
        f"The search index (Qdrant, {where}) is unavailable: {type(exc).__name__}."
    )


@lru_cache
def get_schema_index() -> SchemaIndex:
    """One client per process. FastAPI dependency (tests swap in an in-memory one)."""
    if settings.qdrant_url:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = AsyncQdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=10)
    else:
        # Embedded: a folder, locked by this process (a second process can't open it).
        client = AsyncQdrantClient(path=settings.qdrant_path)
    return SchemaIndex(
        client, settings.qdrant_collection, get_embedder().dense_dim, local=not settings.qdrant_url
    )
