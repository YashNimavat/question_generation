import sqlite3

import pytest

from core.enums import OperationType
from db.repositories import metadata_repo
from metadata.logger import log_call


def test_log_call_persists_retrievable_record(db_path):
    record = log_call(
        operation_type=OperationType.GENERATION,
        provider="groq",
        model="llama3-70b",
        input_tokens=100,
        output_tokens=200,
        latency_ms=500.0,
        cost_usd=0.001,
        prompt_version="mcq_v1",
        db_path=db_path,
    )

    fetched = metadata_repo.get(record.id, db_path=db_path)
    assert fetched == record
    assert fetched.operation_type == OperationType.GENERATION


def test_log_call_records_rag_usage(db_path):
    record = log_call(
        operation_type=OperationType.GENERATION,
        provider="groq",
        model="llama3-70b",
        input_tokens=100,
        output_tokens=200,
        latency_ms=500.0,
        cost_usd=0.001,
        rag_usage={"document_id": "doc-1", "chunk_ids": ["c1"]},
        db_path=db_path,
    )

    fetched = metadata_repo.get(record.id, db_path=db_path)
    assert fetched.rag_usage == {"document_id": "doc-1", "chunk_ids": ["c1"]}


def test_log_call_propagates_repository_failures(tmp_path):
    uninitialized_db = tmp_path / "no_schema.db"

    with pytest.raises(sqlite3.OperationalError):
        log_call(
            operation_type=OperationType.EVALUATION,
            provider="groq",
            model="llama3-70b",
            input_tokens=10,
            output_tokens=20,
            latency_ms=100.0,
            cost_usd=0.0001,
            db_path=uninitialized_db,
        )
