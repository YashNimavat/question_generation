from rag.retrieval import RetrievedChunk


def build_grounded_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[chunk {chunk.chunk_id}]\n{chunk.text}" for chunk in chunks)
