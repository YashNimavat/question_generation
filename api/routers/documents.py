from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from api.deps import get_db_path, get_embedding_provider_dep, get_vector_store_dep
from core.models import Document
from db.repositories import documents_repo
from embeddings.base import EmbeddingProvider
from rag.vector_store import VectorStore
from services.ingestion import IngestionError, ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=Document)
def upload_document(
    file: UploadFile,
    title: Annotated[str, Form()],
    topic: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
    db_path: Path = Depends(get_db_path),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider_dep),
    vector_store: VectorStore | None = Depends(get_vector_store_dep),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    try:
        return ingest_document(
            file_bytes=file.file.read(),
            filename=file.filename or "upload",
            title=title,
            topic=topic,
            tags=tag_list,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            db_path=db_path,
        )
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{document_id}", response_model=Document)
def get_document(document_id: str, db_path: Path = Depends(get_db_path)):
    document = documents_repo.get(document_id, db_path=db_path)
    if document is None:
        raise HTTPException(404, f"No document found for id={document_id!r}")
    return document
