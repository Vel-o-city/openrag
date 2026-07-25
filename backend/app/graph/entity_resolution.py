"""Deliberately lightweight entity resolution: bias toward creating a new
entity over an uncertain merge, since a false split is a cosmetic blemish but
a false merge corrupts information. Four signals, checked in order, any one
of which is enough to call it a match: exact normalized-name match, token
subset match, fuzzy string similarity, then embedding cosine similarity.

Cross-lingual alias resolution and ML clustering-based resolution are
explicitly out of scope for v1.
"""

import re
import unicodedata

from rapidfuzz import fuzz

FUZZY_MATCH_THRESHOLD = 85
EMBEDDING_SIMILARITY_THRESHOLD = 0.92


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s]", "", normalized).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def _token_subset_match(a: str, b: str) -> bool:
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return False
    return tokens_a <= tokens_b or tokens_b <= tokens_a


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_best_candidate(
    name_normalized: str,
    embedding: list[float] | None,
    candidates: list[dict],
) -> dict | None:
    """candidates: fulltext-shortlisted entities of the same coarse type, each
    a dict with at least `name_normalized`, optionally `embedding`. Returns the
    best-matching candidate if any signal clears its threshold, else None
    (caller should create a new entity)."""
    for candidate in candidates:
        if candidate["name_normalized"] == name_normalized:
            return candidate

    for candidate in candidates:
        if _token_subset_match(name_normalized, candidate["name_normalized"]):
            return candidate

    best_fuzzy, best_fuzzy_score = None, 0.0
    for candidate in candidates:
        score = fuzz.ratio(name_normalized, candidate["name_normalized"])
        if score > best_fuzzy_score:
            best_fuzzy, best_fuzzy_score = candidate, score
    if best_fuzzy is not None and best_fuzzy_score >= FUZZY_MATCH_THRESHOLD:
        return best_fuzzy

    if embedding is not None:
        best_embed, best_sim = None, 0.0
        for candidate in candidates:
            if not candidate.get("embedding"):
                continue
            sim = cosine_similarity(embedding, candidate["embedding"])
            if sim > best_sim:
                best_embed, best_sim = candidate, sim
        if best_embed is not None and best_sim >= EMBEDDING_SIMILARITY_THRESHOLD:
            return best_embed

    return None
