from app.ingestion.chunking import OVERLAP_CHARS, TARGET_CHARS, chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_short_text_is_single_chunk():
    text = "A short paragraph that easily fits in one chunk."
    assert chunk_text(text) == [text]


def test_chunk_text_splits_long_text_into_multiple_chunks():
    paragraph = "This is one sentence in a paragraph. " * 40  # ~1520 chars
    text = "\n\n".join([paragraph] * 5)  # well over TARGET_CHARS

    chunks = chunk_text(text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= TARGET_CHARS + OVERLAP_CHARS


def test_chunk_text_reassembles_to_roughly_the_same_content():
    paragraph = "Sentence number %d in the document. "
    text = "\n\n".join(paragraph % i for i in range(200))

    chunks = chunk_text(text)
    rejoined = "".join(chunks)

    # every chunk boundary overlaps content rather than dropping it
    assert "Sentence number 0 " in rejoined
    assert "Sentence number 199" in rejoined


def test_chunk_text_handles_single_giant_word_with_hard_split():
    text = "x" * (TARGET_CHARS * 3)

    chunks = chunk_text(text)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= TARGET_CHARS + OVERLAP_CHARS
