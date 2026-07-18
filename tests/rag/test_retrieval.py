from db.connection import get_connection
from rag.retrieval import get_relevant_chunks
from tests.factories import FakeEmbeddingProvider, FakeVectorStore, make_embedding_result


def test_get_relevant_chunks_embeds_query_and_filters_by_document(db_path):
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = FakeVectorStore()
    vector_store.add(
        ids=["doc1_0", "doc1_1"],
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        metadata=[
            {"document_id": "doc1", "chunk_index": 0, "text": "alpha", "start_char": 0, "end_char": 5},
            {"document_id": "doc1", "chunk_index": 1, "text": "beta", "start_char": 5, "end_char": 9},
        ],
    )
    vector_store.add(
        ids=["doc2_0"],
        vectors=[[1.0, 0.0]],
        metadata=[{"document_id": "doc2", "chunk_index": 0, "text": "gamma", "start_char": 0, "end_char": 5}],
    )

    chunks = get_relevant_chunks(
        query="what is alpha",
        document_id="doc1",
        top_k=5,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    assert [c.chunk_id for c in chunks] == ["doc1_0", "doc1_1"]
    assert chunks[0].document_id == "doc1"
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "alpha"

    assert embedding_provider.calls == [
        {"texts": ["what is alpha"], "model": "embed-english-v3.0", "input_type": "search_query"}
    ]
    assert vector_store.queried[0]["filter"] == {"document_id": "doc1"}
    assert vector_store.queried[0]["top_k"] == 5


def test_get_relevant_chunks_respects_top_k(db_path):
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = FakeVectorStore()
    vector_store.add(
        ids=["doc1_0", "doc1_1", "doc1_2"],
        vectors=[[1.0, 0.0]] * 3,
        metadata=[
            {"document_id": "doc1", "chunk_index": i, "text": f"chunk {i}", "start_char": 0, "end_char": 1}
            for i in range(3)
        ],
    )

    chunks = get_relevant_chunks(
        query="topic",
        document_id="doc1",
        top_k=2,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    assert len(chunks) == 2


def test_get_relevant_chunks_returns_empty_list_when_no_matches(db_path):
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = FakeVectorStore()

    chunks = get_relevant_chunks(
        query="topic",
        document_id="doc1",
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    assert chunks == []


def test_get_relevant_chunks_logs_embedding_metadata(db_path):
    embedding_provider = FakeEmbeddingProvider(
        [make_embedding_result(vectors=[[1.0, 0.0]], input_tokens=42, cost_usd=0.0001)]
    )
    vector_store = FakeVectorStore()

    get_relevant_chunks(
        query="topic",
        document_id="doc1",
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM metadata_logs").fetchall()
    assert len(rows) == 1
    assert rows[0]["operation_type"] == "embedding"
    assert rows[0]["input_tokens"] == 42
    assert rows[0]["cost_usd"] == 0.0001
