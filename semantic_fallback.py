
import os
import pickle
import hashlib
import numpy as np

"""
semantic_fallback.py
---------------------
Semantic-similarity fallback for ethnic_tagger_v3.py.

This module is consulted ONLY for funding requests the deterministic
rule engine in ethnic_tagger_v3.py could not classify (rows that
resolved to General Population). It never overrides or auto-writes a
final Ethnic 1/2/3 result on its own, it only adds a flagged
suggestion column for manual review, because embedding similarity does
not understand negation, context override, or the other edge cases
the deterministic engine already handles correctly. See the "Why this
is a fallback, not a replacement" discussion in the project notes.

How it works:
    1. Build one short text per unique taxonomy entry, combining the
       Level 1/2/3 term names with the Level 1 "Definitions and Scope
       Notes" text where available (see TAXONOMY_SCOPE_NOTES in
       ethnic_tagger_v3.py's source taxonomy sheet).
    2. Embed all of those texts once with a local sentence-embedding
       model and cache the result to disk, keyed by a hash of the
       texts, so unchanged taxonomy isn't re-embedded on every run.
    3. For each row the deterministic engine couldn't place, embed its
       combined text the same way and find the closest taxonomy entry
       by cosine similarity.
    4. Only surface a suggestion if the similarity clears
       SIMILARITY_THRESHOLD. Below that, return None and leave the row
       as General Population with no added column value.

Requires: sentence-transformers
    pip install sentence-transformers --break-system-packages

Runs entirely locally once the model is downloaded — no API calls, no
funding request text leaves this machine. The first run on a new
machine will download the model from Hugging Face (a few hundred MB),
which requires a normal internet connection; after that it's cached
locally and works offline.
"""

MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.55
CACHE_DIR = ".semantic_cache"

model = None

def get_model():
    """
    Load the embedding model so importing this module doesn't
    require sentence-transformers (or trigger a model download) unless
    the semantic step actually runs.
    """
    global model
    if model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL_NAME)
    return model

def build_scope_note_map(tax_df, level1_col, scope_notes_col, safe_display_fn):
    """
    Map each Level 1 category to its definition/scope note text.
    Scope notes are only populated on Level 1 rows in the real
    taxonomy sheet, so this collects the first non-empty note seen
    for each Level 1 value and ignores blank cells on deeper rows.
    """
    notes = {}
    for _, row in tax_df.iterrows():
        l1 = safe_display_fn(row.get(level1_col, ""))
        note = safe_display_fn(row.get(scope_notes_col, ""))
        if l1 and note and l1 not in notes:
            notes[l1] = note
    return notes

def build_candidate_texts(taxonomy_entries, scope_notes):
    """
    Build one embedding-ready text string per unique (level1, level2,
    level3) taxonomy entry, combining the term names with the Level 1
    scope note where available. Deduplicates entries that share the
    same level1/level2/level3 combination (taxonomy_entries may contain
    repeats since it's built per taxonomy row).

    Returns (unique_entries, texts) — parallel lists, same order.
    """
    seen = set()
    unique_entries = []
    texts = []
    for e in taxonomy_entries:
        key = (e["level1"], e["level2"], e["level3"])
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append(e)

        parts = [p for p in [e["level1"], e["level2"], e["level3"]] if p]
        text = ", ".join(parts)
        note = scope_notes.get(e["level1"], "")
        if note:
            text += ". " + note
        texts.append(text)

    return unique_entries, texts

def cache_key(texts):
    joined = "||".join(texts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

def get_taxonomy_embeddings(texts):
    """
    Embed all taxonomy candidate texts, caching the result to disk
    keyed by a hash of the texts themselves so unchanged taxonomy
    doesn't get re-embedded on every run. Cache is invalidated
    automatically the moment the taxonomy text changes, since the
    hash changes with it.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = cache_key(texts)
    cache_path = os.path.join(CACHE_DIR, f"taxonomy_emb_{key}.pkl")

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)

    with open(cache_path, "wb") as f:
        pickle.dump(embeddings, f)

    return embeddings

def find_semantic_suggestion(text, unique_entries, taxonomy_embeddings):
    """
    Embed the funding request's combined text and return the best-
    matching taxonomy entry above SIMILARITY_THRESHOLD, or None if
    nothing clears the bar (including for empty input).

    Returns (level1, level2, level3, score) or None.
    """
    if not text.strip():
        return None

    model = get_model()
    query_embedding = model.encode([text], normalize_embeddings=True)[0]

    # Embeddings are normalized
    scores = taxonomy_embeddings @ query_embedding
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    if best_score < SIMILARITY_THRESHOLD:
        return None

    best_entry = unique_entries[best_idx]
    return (best_entry["level1"], best_entry["level2"], best_entry["level3"], best_score)