from rag.vector_store import ChromaVectorStore


def test_add_and_query_round_trip(tmp_path):
    store = ChromaVectorStore(persist_dir=tmp_path)

    store.add(
        ids=["doc1_0", "doc1_1"],
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        metadata=[
            {"document_id": "doc1", "chunk_index": 0, "text": "alpha"},
            {"document_id": "doc1", "chunk_index": 1, "text": "beta"},
        ],
    )

    matches = store.query(vector=[1.0, 0.0], top_k=1)

    assert len(matches) == 1
    assert matches[0].id == "doc1_0"
    assert matches[0].metadata["text"] == "alpha"


def test_query_returns_top_k_closest_matches(tmp_path):
    store = ChromaVectorStore(persist_dir=tmp_path)
    store.add(
        ids=["a", "b", "c"],
        vectors=[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
        metadata=[{"i": 0}, {"i": 1}, {"i": 2}],
    )

    matches = store.query(vector=[1.0, 0.0], top_k=2)

    assert len(matches) == 2
    assert matches[0].id == "a"


def test_query_applies_metadata_filter(tmp_path):
    store = ChromaVectorStore(persist_dir=tmp_path)
    store.add(
        ids=["a", "b"],
        vectors=[[1.0, 0.0], [1.0, 0.0]],
        metadata=[{"document_id": "doc1"}, {"document_id": "doc2"}],
    )

    matches = store.query(vector=[1.0, 0.0], top_k=5, filter={"document_id": "doc2"})

    assert [m.id for m in matches] == ["b"]


def test_custom_collection_name_is_isolated_from_default(tmp_path):
    chunks_store = ChromaVectorStore(persist_dir=tmp_path)
    questions_store = ChromaVectorStore(
        persist_dir=tmp_path, collection_name="questions", metadata={"hnsw:space": "cosine"}
    )

    chunks_store.add(ids=["chunk1"], vectors=[[1.0, 0.0]], metadata=[{"text": "a chunk"}])
    questions_store.add(ids=["q1_1"], vectors=[[1.0, 0.0]], metadata=[{"question_id": "q1"}])

    assert [m.id for m in chunks_store.query(vector=[1.0, 0.0], top_k=5)] == ["chunk1"]
    assert [m.id for m in questions_store.query(vector=[1.0, 0.0], top_k=5)] == ["q1_1"]
