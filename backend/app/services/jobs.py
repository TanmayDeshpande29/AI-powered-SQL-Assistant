"""Shared plumbing for background jobs (uploads, search indexing).

Jobs run after the HTTP response is sent, so they can't use the request's database
session: they get a session *factory* and everything else they need in one bundle.
"""

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.client import LLMProvider
from app.rag.embeddings import Embedder
from app.rag.vector_store import SchemaIndex


@dataclass(frozen=True)
class JobDeps:
    session_factory: async_sessionmaker[AsyncSession]
    llm: LLMProvider
    embedder: Embedder
    index: SchemaIndex


# One job at a time per schema: merging an upload and re-indexing the same schema must
# not interleave. Process-local; a distributed queue would use a per-schema job key.
_schema_locks: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


def schema_lock(schema_id: uuid.UUID) -> asyncio.Lock:
    return _schema_locks[schema_id]
