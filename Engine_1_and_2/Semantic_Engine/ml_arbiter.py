import os
import hashlib
from pathlib import Path

import numpy as np
from ethnic_taggerv3 import get_body_and_name_texts

"""
ml_arbiter.py
-------------
ML AUGMENTATION LAYER — Phase A foundation (embed / knn / nli_role helpers)
plus the Phase B wiring point: classify_pipeline.apply_ml_role_arbiter()
calls nli_role() to re-score regex "served" role tags, gated behind the
USE_ML_ROLE_ARBITER env var (default off — no behavior change to the
shipping rule-only path). resolver.py and Gender_SexID.py still never
import this module directly; only classify_pipeline.py does, and only
inside the flag-gated call.

Offline-only: both models are loaded exclusively from the local vendored
directory (see vendor_models.py) with HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE
set before any HF import touches the network. If a model hasn't been
vendored yet, loading raises a clear error rather than silently falling
back to a network download.

Models (frozen, CPU-only, safetensors-only):
    encoder : intfloat/multilingual-e5-small   (embed / knn)
    NLI     : cross-encoder/nli-deberta-v3-small (nli_role)
"""

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

SEMANTIC_ENGINE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SEMANTIC_ENGINE_DIR / "models"
ENCODER_DIR = MODELS_DIR / "intfloat__multilingual-e5-small"
NLI_DIR = MODELS_DIR / "cross-encoder__nli-deberta-v3-small"

CACHE_DIR = SEMANTIC_ENGINE_DIR.parent.parent / ".ml_cache"

# Role hypotheses scored by nli_role() — the five Phase 2 regex-based role
# frames in extractors.py/ethnic_taggerv3.infer_role, plus "topic",
# "aspirational", and "allyship" (added to catch weak-role families the regex
# frames only recognize via a narrow anchored phrase list — see
# ROLE_TOPIC_AFTER_PATTERNS / ASPIRATIONAL_PHRASES / ROLE_ALLYSHIP_BEFORE_PATTERNS
# in constants.py). "allyship" gets its own hypothesis even though the regex
# frame collapses it into the "topic" role string (infer_role, "Reuses the
# weak 'topic' role") — the arbiter never sets `role` at all, so it only
# needs a hypothesis that discriminates well semantically, and "topic"'s
# wording ("a subject being taught") is a poor match for solidarity/
# partnership language. Adding a hypothesis here never changes
# classify_pipeline output on its own — see apply_ml_role_arbiter, which only
# ever attaches an annotation, never a role or label change.
ROLE_HYPOTHESES = {
    "served": "This text describes who the program serves.",
    "org_name": "This is the name of an organization or partner.",
    "provider": "This describes a service provider or professional role, not who is served.",
    "example": "This is an example or illustrative mention, not a description of who is served.",
    "negated": "This population is explicitly excluded or not served.",
    "topic": "This text names a subject or perspective being taught or discussed, not a population being served.",
    "aspirational": "This describes a future goal or planned expansion, not the population currently served.",
    "allyship": "This describes the organization's support for, partnership with, or solidarity with a group, not the group as the population served.",
    # Cultural-origin / attribution. Distinct from "topic": the group is named
    # as the SOURCE a practice, method, story, or teaching was drawn from --
    # "the story circle, adapted from First Nation Indigenous community
    # peacemaking practices", "a talking circle grounded in Cree tradition",
    # "integrating Indigenous wisdom". The regex side only covers a narrow
    # fixed list (ROLE_SETTING_BEFORE_PATTERNS: "based on"/"inspired by"/
    # "set in"/"depicting"), so near-synonyms like "adapted from", "drawn
    # from", "rooted in", "grounded in", "informed by" fall through to the
    # "served" default and produce a false positive. This is the single
    # largest false-positive family in the AUDITED_FR_GOLD.xlsx audit.
    "cultural_origin": (
        "This names the cultural tradition, practice, or knowledge system that "
        "something was adapted, derived, or drawn from, not the population being served."
    ),
}

_encoder = None
_nli = None

def require_vendor(model_dir: Path, repo_id: str):
    if not (model_dir / "MANIFEST.sha256").exists():
        raise RuntimeError(
            f"{repo_id} is not vendored. Run:\n"
            f'  .venv\\Scripts\\python.exe "Engine 1 and 2/Semantic Engine/vendor_models.py"'
        )

def get_encoder():
    """Lazy-load the multilingual-e5-small encoder from the vendored,
    offline directory. Importing this module never triggers a model load."""
    global _encoder
    if _encoder is None:
        require_vendor(ENCODER_DIR, "intfloat/multilingual-e5-small")
        from sentence_transformers import SentenceTransformer
        _encoder = SentenceTransformer(str(ENCODER_DIR))
    return _encoder

def get_nli():
    """Lazy-load the NLI cross-encoder from the vendored, offline directory."""
    global _nli
    if _nli is None:
        require_vendor(NLI_DIR, "cross-encoder/nli-deberta-v3-small")
        from sentence_transformers import CrossEncoder
        _nli = CrossEncoder(str(NLI_DIR))
    return _nli

def embed(text: str, kind: str = "query") -> np.ndarray:
    """
    Embed text with the vendored multilingual-e5-small encoder.

    kind: "query" or "passage" — E5 models are instruction-tuned on these
    two prefixes and produce noticeably worse similarity scores without
    one. Use "query" for a funding-request row being looked up; "passage"
    for gold-corpus entries being indexed.
    """
    if kind not in ("query", "passage"):
        raise ValueError('kind must be "query" or "passage"')
    if not text or not text.strip():
        return np.zeros(get_encoder().get_embedding_dimension(), dtype=np.float32)
    prefixed = f"{kind}: {text.strip()}"
    vec = get_encoder().encode([prefixed], normalize_embeddings=True)[0]
    return np.asarray(vec, dtype=np.float32)

def cache_key(*parts) -> str:
    joined = "||".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

def build_gold_embedding_store(gold_rows, force: bool = False):
    """
    Embed each gold-audited row's body and name text SEPARATELY (Plan.md:
    "reuse get_body_and_name_texts to embed body and name separately") and
    cache the result to disk, keyed by a hash of the input texts so the
    store is automatically invalidated when the gold file changes.

    gold_rows: list of dicts, each with at least "id" and the columns
        get_body_and_name_texts() expects (Final_Project_Description,
        Final_Summary_Description, Purpose, Funding Request Name).

    Returns a dict: {"ids": [...], "body_vecs": np.ndarray (N, D),
                     "name_vecs": np.ndarray (N, D)}
    """

    ids, bodies, names = [], [], []
    for row in gold_rows:
        body_text, name_text = get_body_and_name_texts(row)
        ids.append(row.get("id") or row.get("SF_18_ID_Funding_Request__c") or "")
        bodies.append(body_text)
        names.append(name_text)

    key = cache_key(*ids, *bodies, *names)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"gold_store_{key}.npz"

    if cache_path.exists() and not force:
        # allow_pickle=False: an .npz of plain string/float arrays can never
        # execute code on load, unlike the previous pickle cache (Plan.md
        # no-pickle / sensitive-data-at-rest rule).
        with np.load(cache_path, allow_pickle=False) as data:
            return {"ids": [str(x) for x in data["ids"]],
                    "body_vecs": data["body_vecs"],
                    "name_vecs": data["name_vecs"]}

    body_vecs = np.stack([embed(t, kind="passage") for t in bodies]) if bodies else np.zeros((0, 1))
    name_vecs = np.stack([embed(t, kind="passage") for t in names]) if names else np.zeros((0, 1))
    store = {"ids": ids, "body_vecs": body_vecs, "name_vecs": name_vecs}

    # ids saved as a unicode (not object) array so it reloads under allow_pickle=False.
    np.savez(cache_path, ids=np.array(ids), body_vecs=body_vecs, name_vecs=name_vecs)
    return store

def faiss_index(vecs: np.ndarray):
    import faiss
    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)  # vectors are already L2-normalized -> inner product == cosine
    if len(vecs):
        index.add(vecs.astype(np.float32))
    return index

def knn(vec: np.ndarray, k: int, store: dict, field: str = "body_vecs"):
    """
    k nearest neighbors of `vec` in the cached gold-embedding store, by
    cosine similarity (vectors are pre-normalized, so inner product ==
    cosine). `store` is the dict returned by build_gold_embedding_store().

    Returns a list of (gold_id, similarity) tuples, closest first.
    """
    if field not in ("body_vecs", "name_vecs"):
        raise ValueError('field must be "body_vecs" or "name_vecs"')
    vecs = store[field]
    if len(vecs) == 0:
        return []
    index = faiss_index(vecs)
    k = min(k, len(vecs))
    scores, idxs = index.search(vec.reshape(1, -1).astype(np.float32), k)
    return [(store["ids"][i], float(s)) for s, i in zip(scores[0], idxs[0]) if i != -1]

def nli_role(span: str, text: str) -> dict:
    """
    Zero-shot evidence-role scoring for an identity span found in text,
    using the vendored NLI cross-encoder (Plan.md Phase B intent — this
    Phase A helper just exposes the scoring primitive, not yet wired into
    the resolver).

    Scores each of ROLE_HYPOTHESES as a (premise, hypothesis) pair, where
    the premise is the local context with the target span wrapped in
    double-quotes so the model knows which occurrence the role hypotheses
    are about (a raw context window can otherwise contain more than one
    identity term — e.g. both "Black" and "African" — with different
    roles), and returns {role: entailment_score, ...} plus "best_role" —
    the role whose hypothesis the model finds most entailed by the premise.

    This backs up / could eventually replace the regex-based role frames
    in extractors.py / ethnic_taggerv3.infer_role() (see Phase B), and is
    intended to generalize to phrasings the regex frames don't cover.
    """
    span = span.strip()
    context = text.strip()
    if span and context:
        idx = context.lower().find(span.lower())
        if idx != -1:
            premise = f'{context[:idx]}"{context[idx:idx + len(span)]}"{context[idx + len(span):]}'
        else:
            premise = f'{context} (term: "{span}")'
    else:
        premise = context or span
    pairs = [(premise, hyp) for hyp in ROLE_HYPOTHESES.values()]
    raw_scores = get_nli().predict(pairs)  # shape (n_hypotheses, 3): [contradiction, entailment, neutral]
    raw_scores = np.asarray(raw_scores)
    entailment_scores = raw_scores[:, 1] if raw_scores.ndim == 2 else raw_scores

    result = {role: float(score) for role, score in zip(ROLE_HYPOTHESES, entailment_scores)}
    result["best_role"] = max(result, key=result.get)
    return result
