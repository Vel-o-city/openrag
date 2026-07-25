from app.chat.guardrails import find_unverified_urls


def test_finds_no_urls_in_a_plain_answer():
    assert find_unverified_urls("Helix Labs is based in Austin.", ["Helix Labs source text."]) == []


def test_flags_a_url_not_present_in_any_source_chunk():
    answer = "You can read more at https://evil-injected-link.example/phish."
    assert find_unverified_urls(answer, ["Helix Labs source text, no links here."]) == [
        "https://evil-injected-link.example/phish."
    ]


def test_does_not_flag_a_url_that_appears_verbatim_in_a_source_chunk():
    url = "https://legit-source.example/report"
    answer = f"See the original report at {url} for details."
    assert find_unverified_urls(answer, [f"Published here: {url}"]) == []


def test_flags_only_the_unverified_url_among_several():
    good_url = "https://legit-source.example/report"
    bad_url = "https://evil-injected-link.example/phish"
    answer = f"Sources: {good_url} and {bad_url}."
    assert find_unverified_urls(answer, [f"Original: {good_url}"]) == [bad_url + "."]
