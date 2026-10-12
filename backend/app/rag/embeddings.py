"""Text -> vectors, with Hugging Face models run locally (fastembed + ONNX Runtime).

Two kinds of vector per text:
  dense   384 floats from BAAI/bge-small-en-v1.5: *meaning*. "revenue" lands near
          "sales" and "total_amount" even with no word in common.
  sparse  {token id: weight} from Qdrant/bm25: *exact words*, as in classic keyword
          search. Great for identifiers and rare terms ("sku", "iban"), blind to synonyms.
Phase 4 searches with both and fuses the rankings (hybrid search).

Why fastembed instead of sentence-transformers? Same Hugging Face models, exported to
ONNX: no PyTorch (a ~2 GB dependency), fast on a CPU, and it ships the BM25 model too.
Models download once from the Hugging Face Hub into settings.embedding_cache_dir.

Everything here is synchronous CPU work: async callers wrap it in asyncio.to_thread()
so the event loop keeps serving requests while a batch is embedded.
"""

import logging
import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import EmbeddingError

# Windows without developer mode can't create the symlinks the HF cache prefers; it
# falls back to copies, which is fine, so silence the warning about it.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from fastembed import SparseTextEmbedding, TextEmbedding  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]  # token ids (hashes of stemmed words)
    values: list[float]  # how often each appears (Qdrant multiplies in the IDF at search time)


@dataclass(frozen=True)
class Embedding:
    dense: list[float]
    sparse: SparseVector


class Embedder(Protocol):
    """What the rest of the app needs; tests plug in a fake with the same shape."""

    dense_model: str
    sparse_model: str

    @property
    def dense_dim(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[Embedding]: ...

    def embed_query(self, text: str) -> Embedding: ...


class FastEmbedEmbedder:
    def __init__(self, dense_model: str, sparse_model: str, cache_dir: str, batch_size: int):
        self.dense_model = dense_model
        self.sparse_model = sparse_model
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._lock = threading.Lock()  # two first requests must not both load the models
        self._dense: TextEmbedding | None = None
        self._sparse: SparseTextEmbedding | None = None

    @property
    def dense_dim(self) -> int:
        # Looked up in fastembed's model table: no download needed.
        return TextEmbedding.get_embedding_size(self.dense_model)

    def _models(self) -> tuple[TextEmbedding, SparseTextEmbedding]:
        with self._lock:
            if self._dense is None or self._sparse is None:
                logger.info("Loading embedding models %s + %s", self.dense_model, self.sparse_model)
                try:
                    self._dense = TextEmbedding(self.dense_model, cache_dir=self._cache_dir)
                    self._sparse = SparseTextEmbedding(self.sparse_model, cache_dir=self._cache_dir)
                except Exception as exc:
                    logger.exception("Could not load the embedding models")
                    raise EmbeddingError(
                        "The embedding models could not be loaded. The first run downloads "
                        "them from Hugging Face (~80 MB): check the internet connection."
                    ) from exc
            return self._dense, self._sparse

    def embed_documents(self, texts: list[str]) -> list[Embedding]:
        if not texts:
            return []
        dense_model, sparse_model = self._models()
        dense = dense_model.embed(texts, batch_size=self._batch_size)
        sparse = sparse_model.embed(texts, batch_size=self._batch_size)
        return [_embedding(d, s) for d, s in zip(dense, sparse, strict=True)]

    def embed_query(self, text: str) -> Embedding:
        # query_embed: some models encode questions differently from documents.
        dense_model, sparse_model = self._models()
        return _embedding(
            next(iter(dense_model.query_embed(text))), next(iter(sparse_model.query_embed(text)))
        )


def _embedding(dense, sparse) -> Embedding:
    return Embedding(
        dense=[float(x) for x in dense],
        sparse=SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist()),
    )


@lru_cache
def get_embedder() -> Embedder:
    """One instance per process (models are loaded lazily, on first use). FastAPI dependency."""
    return FastEmbedEmbedder(
        settings.embedding_model_dense,
        settings.embedding_model_sparse,
        settings.embedding_cache_dir,
        settings.embedding_batch_size,
    )
