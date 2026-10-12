"""Uploaded database schemas: CRUD + uploads (processed in the background) + search.

Upload flow:  POST .../sources/text | .../sources/file
              -> 202 Accepted + the source (status "pending")
              -> the client polls GET .../sources/{id} until "ready" or "failed".
Uploading the same content again returns the existing source with 200 (idempotent).

Phase 3: every successful upload also refreshes the schema's search index (index_status
on the schema). POST .../index rebuilds it on demand; GET .../search queries it.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, Embeddings, Jobs, VectorIndex
from app.db.session import release_connection
from app.rag.vector_store import SearchMode
from app.schemas.db_schema import (
    SchemaCreate,
    SchemaDetail,
    SchemaSummary,
    SchemaUpdate,
    SearchResponse,
    SourceRead,
    SourceTextCreate,
)
from app.services import indexing, ingestion
from app.services import schemas as service

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("", response_model=list[SchemaSummary])
async def list_schemas(user: CurrentUser, db: DbSession):
    return await service.list_schemas(db, user.id)


@router.post("", response_model=SchemaSummary, status_code=status.HTTP_201_CREATED)
async def create_schema(data: SchemaCreate, user: CurrentUser, db: DbSession):
    schema = await service.create_schema(db, user.id, data)
    [summary] = await service.summaries(db, [schema])
    return summary


@router.get("/{schema_id}", response_model=SchemaDetail)
async def get_schema(schema_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.schema_detail(db, user.id, schema_id)


@router.patch("/{schema_id}", response_model=SchemaSummary)
async def update_schema(schema_id: uuid.UUID, data: SchemaUpdate, user: CurrentUser, db: DbSession):
    schema = await service.update_schema(db, user.id, schema_id, data)
    [summary] = await service.summaries(db, [schema])
    return summary


@router.delete("/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(schema_id: uuid.UUID, user: CurrentUser, db: DbSession, index: VectorIndex):
    await service.delete_schema(db, user.id, schema_id)
    await indexing.forget_schema(index, schema_id)  # its vectors go too


@router.delete("/{schema_id}/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    schema_id: uuid.UUID,
    table_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    jobs: Jobs,
    background: BackgroundTasks,
):
    await service.delete_table(db, user.id, schema_id, table_id)
    # Re-index: drops the table's point and refreshes tables that referenced it.
    background.add_task(indexing.run_index_job, schema_id, jobs)


@router.post(
    "/{schema_id}/index", response_model=SchemaSummary, status_code=status.HTTP_202_ACCEPTED
)
async def rebuild_index(
    schema_id: uuid.UUID, user: CurrentUser, db: DbSession, jobs: Jobs, background: BackgroundTasks
):
    """(Re)build the search index in the background. Unchanged tables are skipped."""
    schema = await service.get_owned(db, user.id, schema_id)
    await indexing.mark_pending(db, schema)
    background.add_task(indexing.run_index_job, schema_id, jobs)
    [summary] = await service.summaries(db, [schema])
    return summary


@router.get("/{schema_id}/search", response_model=SearchResponse)
async def search(
    schema_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    embedder: Embeddings,
    index: VectorIndex,
    q: Annotated[str, Query(min_length=2, max_length=500, description="A question or keywords")],
    mode: SearchMode = "dense",
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    """Find the tables most related to `q`: by meaning (dense) or by keywords (sparse/BM25)."""
    schema = await service.get_owned(db, user.id, schema_id)  # 404 if not yours
    await release_connection(db)  # the first query may load the models (seconds)
    return await indexing.search_tables(
        db,
        user_id=user.id,
        schema=schema,
        query=q,
        mode=mode,
        limit=limit,
        embedder=embedder,
        index=index,
    )


@router.get("/{schema_id}/sources", response_model=list[SourceRead])
async def list_sources(schema_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.list_sources(db, user.id, schema_id)


@router.get("/{schema_id}/sources/{source_id}", response_model=SourceRead)
async def get_source(schema_id: uuid.UUID, source_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await service.get_source(db, user.id, schema_id, source_id)


@router.post(
    "/{schema_id}/sources/text",
    response_model=SourceRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def add_sql_text(
    schema_id: uuid.UUID,
    data: SourceTextCreate,
    user: CurrentUser,
    db: DbSession,
    jobs: Jobs,
    background: BackgroundTasks,
    response: Response,
):
    schema = await service.get_owned(db, user.id, schema_id)
    source, queued = await service.add_source(db, schema, kind="sql_text", text=data.sql)
    if queued:
        # Runs after the response is sent, in this process (see services/ingestion.py).
        background.add_task(ingestion.process_source, source.id, jobs)
    else:
        response.status_code = status.HTTP_200_OK  # the same SQL was uploaded before
    return service.source_read(source)


@router.post(
    "/{schema_id}/sources/file",
    response_model=SourceRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def add_file(
    schema_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    jobs: Jobs,
    background: BackgroundTasks,
    response: Response,
    file: Annotated[
        UploadFile, File(description="A .sql/.txt/.ddl file or a PNG/JPEG/WebP screenshot")
    ],
):
    schema = await service.get_owned(db, user.id, schema_id)
    data = await file.read()
    kind, content_type = service.classify_upload(file.filename, data)
    service.check_size(kind, len(data))
    if kind == "image":
        source, queued = await service.add_source(
            db, schema, kind=kind, raw=data, filename=file.filename, content_type=content_type
        )
    else:
        source, queued = await service.add_source(
            db,
            schema,
            kind=kind,
            text=service.decode_sql_file(data),
            filename=file.filename,
            content_type=content_type,
        )
    if queued:
        background.add_task(ingestion.process_source, source.id, jobs)
    else:
        response.status_code = status.HTTP_200_OK
    return service.source_read(source)
