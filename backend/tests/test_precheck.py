from app.ingestion.precheck import has_usable_native_text, looks_like_readable_text


def test_looks_like_readable_text_accepts_normal_prose():
    assert looks_like_readable_text(
        "This is a perfectly normal sentence extracted from a real PDF page."
    )


def test_looks_like_readable_text_rejects_empty():
    assert not looks_like_readable_text("")
    assert not looks_like_readable_text("   ")


def test_looks_like_readable_text_rejects_too_short():
    assert not looks_like_readable_text("hi")


def test_looks_like_readable_text_rejects_garbage_binary_like_content():
    garbage = "#@$%^&*()_+-=[]{}|;:,.<>/?~`0123456789" * 3  # symbols/digits, no letters
    assert not looks_like_readable_text(garbage)


def test_has_usable_native_text_true_if_any_page_qualifies():
    pages = ["", "", "A real page of readable extracted PDF text content here."]
    assert has_usable_native_text(pages)


def test_has_usable_native_text_false_if_all_pages_are_scans():
    pages = ["", "", ""]
    assert not has_usable_native_text(pages)
