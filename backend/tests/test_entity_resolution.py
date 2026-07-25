from app.graph.entity_resolution import (
    cosine_similarity,
    find_best_candidate,
    normalize_name,
)


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Dr. Jane Doe!") == "dr jane doe"


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Jane   Doe  ") == "jane doe"


def test_normalize_name_strips_accents():
    assert normalize_name("José García") == "jose garcia"


def test_cosine_similarity_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_zero_vector_is_safe():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_find_best_candidate_exact_normalized_match():
    candidates = [{"id": "e1", "name_normalized": "jane doe"}]
    match = find_best_candidate("jane doe", None, candidates)
    assert match is not None
    assert match["id"] == "e1"


def test_find_best_candidate_token_subset_match():
    candidates = [{"id": "e1", "name_normalized": "jane elizabeth doe"}]
    match = find_best_candidate("jane doe", None, candidates)
    assert match is not None
    assert match["id"] == "e1"


def test_find_best_candidate_fuzzy_match_above_threshold():
    candidates = [{"id": "e1", "name_normalized": "jonathan smith"}]
    match = find_best_candidate("jonathon smith", None, candidates)
    assert match is not None
    assert match["id"] == "e1"


def test_find_best_candidate_no_match_below_every_threshold():
    candidates = [{"id": "e1", "name_normalized": "completely different entity"}]
    match = find_best_candidate("jane doe", None, candidates)
    assert match is None


def test_find_best_candidate_empty_candidates_returns_none():
    assert find_best_candidate("jane doe", None, []) is None


def test_find_best_candidate_embedding_similarity_as_fourth_signal():
    candidates = [
        {"id": "e1", "name_normalized": "acme corp inc", "embedding": [1.0, 0.0, 0.0]},
    ]
    # name string itself is too different for fuzzy/token signals to catch,
    # but the embedding is a near-perfect match
    match = find_best_candidate("the acme corporation", [0.99, 0.01, 0.0], candidates)
    assert match is not None
    assert match["id"] == "e1"


def test_find_best_candidate_embedding_below_threshold_creates_new():
    candidates = [
        {"id": "e1", "name_normalized": "acme corp inc", "embedding": [1.0, 0.0, 0.0]},
    ]
    match = find_best_candidate("the acme corporation", [0.5, 0.5, 0.7], candidates)
    assert match is None
