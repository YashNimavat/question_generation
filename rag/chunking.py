import re

from pydantic import BaseModel

# 375 words approximates ~500 tokens at ~0.75 tokens/word, the default suggested in
# docs/TECH_ARCHITECTURE.md SS6.2 ("~500 tokens, ~15% overlap"). No tokenizer dependency
# is used for this approximation, per project convention (no premature abstraction).
DEFAULT_CHUNK_SIZE_WORDS = 375
DEFAULT_OVERLAP_RATIO = 0.15

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WORD_RE = re.compile(r"\S+")


class Chunk(BaseModel):
    document_id: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int


def chunk(
    text: str,
    document_id: str,
    chunk_size_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> list[Chunk]:
    """Fixed-size chunking with overlap, preferring paragraph boundaries. A paragraph
    larger than chunk_size_words on its own is hard-sliced into overlapping word-count
    windows instead."""
    overlap_words = int(chunk_size_words * overlap_ratio)
    segments = _build_segments(text, chunk_size_words, overlap_words)
    if not segments:
        return []

    chunks: list[Chunk] = []
    i = 0
    n = len(segments)
    while i < n:
        j = i
        word_count = 0
        while j < n and word_count + segments[j][2] <= chunk_size_words:
            word_count += segments[j][2]
            j += 1
        if j == i:
            j = i + 1

        start_char = segments[i][0]
        end_char = segments[j - 1][1]
        chunks.append(
            Chunk(
                document_id=document_id,
                chunk_index=len(chunks),
                text=text[start_char:end_char],
                start_char=start_char,
                end_char=end_char,
            )
        )

        if j >= n:
            break  # this chunk already covers every remaining segment

        # carry trailing segments whose combined word count fits the overlap budget
        k = j - 1
        overlap_word_count = 0
        while k >= i and overlap_word_count + segments[k][2] <= overlap_words:
            overlap_word_count += segments[k][2]
            k -= 1
        i = max(k + 1, i + 1)  # always advance at least one segment

    return chunks


def _build_segments(
    text: str, chunk_size_words: int, overlap_words: int
) -> list[tuple[int, int, int]]:
    """Split text into (start_char, end_char, word_count) segments, each no larger
    than chunk_size_words. Paragraphs that fit whole become one segment; a paragraph
    exceeding the budget on its own is hard-sliced into overlapping word windows so
    the ~overlap_ratio guarantee still holds within it."""
    segments: list[tuple[int, int, int]] = []
    stride = max(1, chunk_size_words - overlap_words)
    for para_text, para_start, para_end in _split_paragraphs(text):
        words = list(_WORD_RE.finditer(para_text))
        if len(words) <= chunk_size_words:
            segments.append((para_start, para_end, len(words)))
            continue
        for w_start in range(0, len(words), stride):
            w_end = min(w_start + chunk_size_words, len(words))
            start_char = para_start + words[w_start].start()
            end_char = para_start + words[w_end - 1].end()
            segments.append((start_char, end_char, w_end - w_start))
            if w_end == len(words):
                break
    return segments


def _split_paragraphs(text: str) -> list[tuple[str, int, int]]:
    paragraphs: list[tuple[str, int, int]] = []
    pos = 0
    for part in _PARAGRAPH_SPLIT_RE.split(text):
        start = text.index(part, pos) if part else pos
        if part.strip():
            paragraphs.append((part, start, start + len(part)))
        pos = start + len(part)
    return paragraphs
