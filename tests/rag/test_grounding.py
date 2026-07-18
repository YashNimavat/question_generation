from rag.grounding import build_grounded_context
from rag.retrieval import RetrievedChunk


def _chunk(**overrides) -> RetrievedChunk:
    fields = {
        "chunk_id": "doc1_0",
        "document_id": "doc1",
        "chunk_index": 0,
        "text": "Mitochondria are the powerhouse of the cell.",
        "score": 0.9,
    }
    fields.update(overrides)
    return RetrievedChunk(**fields)


def test_build_grounded_context_includes_chunk_id_and_text():
    context = build_grounded_context([_chunk()])

    assert "doc1_0" in context
    assert "Mitochondria are the powerhouse of the cell." in context


def test_build_grounded_context_joins_multiple_chunks():
    chunks = [
        _chunk(chunk_id="doc1_0", text="alpha"),
        _chunk(chunk_id="doc1_1", chunk_index=1, text="beta"),
    ]

    context = build_grounded_context(chunks)

    assert context.index("alpha") < context.index("beta")
    assert "doc1_0" in context
    assert "doc1_1" in context


def test_build_grounded_context_empty_list_returns_empty_string():
    assert build_grounded_context([]) == ""
