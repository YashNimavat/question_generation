from rag.chunking import chunk


def test_chunk_short_text_returns_single_chunk():
    text = "This is a short document with only a few words."

    chunks = chunk(text, document_id="doc1")

    assert len(chunks) == 1
    assert chunks[0].document_id == "doc1"
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == text
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(text)


def test_chunk_empty_text_returns_no_chunks():
    assert chunk("", document_id="doc1") == []


def test_chunk_respects_paragraph_boundaries():
    para_a = " ".join(f"word{i}" for i in range(200))
    para_b = " ".join(f"word{i}" for i in range(200, 400))
    text = f"{para_a}\n\n{para_b}"

    chunks = chunk(text, document_id="doc1", chunk_size_words=250, overlap_ratio=0.15)

    assert len(chunks) == 2
    assert chunks[0].text == para_a
    assert chunks[1].text == para_b


def test_chunk_produces_overlap_between_consecutive_chunks_in_a_large_paragraph():
    words = [f"word{i}" for i in range(1000)]
    text = " ".join(words)

    chunks = chunk(text, document_id="doc1", chunk_size_words=100, overlap_ratio=0.15)

    assert len(chunks) > 1
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    overlap = set(first_words) & set(second_words)
    assert len(overlap) > 0


def test_chunk_produces_overlap_across_many_small_paragraphs():
    text = "\n\n".join(" ".join(f"p{i}w{j}" for j in range(5)) for i in range(20))

    chunks = chunk(text, document_id="doc1", chunk_size_words=25, overlap_ratio=0.3)

    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:]):
        overlap = set(a.text.split()) & set(b.text.split())
        assert len(overlap) > 0


def test_chunk_back_references_are_valid_offsets():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

    chunks = chunk(text, document_id="doc1")

    for c in chunks:
        assert text[c.start_char : c.end_char] == c.text
        assert c.document_id == "doc1"


def test_chunk_indices_are_sequential():
    text = "\n\n".join(" ".join(f"p{i}w{j}" for j in range(300)) for i in range(5))

    chunks = chunk(text, document_id="doc1", chunk_size_words=250, overlap_ratio=0.15)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_oversized_single_paragraph_is_hard_sliced_within_budget():
    text = " ".join(f"word{i}" for i in range(1000))

    chunks = chunk(text, document_id="doc1", chunk_size_words=100, overlap_ratio=0.1)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text.split()) <= 100
