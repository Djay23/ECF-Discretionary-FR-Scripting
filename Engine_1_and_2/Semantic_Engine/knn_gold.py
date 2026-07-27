import os
import sys
import shutil
import tempfile
from pathlib import Path
from collections import defaultdict

import numpy as np

# ml_arbiter imports ethnic_taggerv3 at module level, so Pipeline has to be on
# sys.path before it is imported -- this module is runnable directly from
# Semantic_Engine, where it otherwise would not be.
_ENGINE_DIR = Path(__file__).resolve().parents[1]
for _p in (_ENGINE_DIR, _ENGINE_DIR / "Pipeline", _ENGINE_DIR / "Semantic_Engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ml_arbiter sets HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE at import, BEFORE any
# transformers/HF import can touch the network, and require_vendor() refuses to
# load a model that isn't in the local vendored dir. Importing it first is what
# makes this module offline-only; do not reorder.
from ml_arbiter import embed, build_gold_embedding_store, ENCODER_DIR, require_vendor

"""
knn_gold.py
-----------
Nearest-neighbour transfer over the HAND-AUDITED gold rows.

Motivation (from the AUDITED_FR_GOLD.xlsx post-mortem): the largest remaining
error family is regex role-frames defaulting to "served" on phrasings nobody
enumerated ("Indigenous-informed", "adapted from First Nation practices"). The
zero-shot NLI arbiter was measured on those rows and could not separate them --
its verdicts swung 6/8 -> 3/8 on a single hypothesis edit, i.e. noise. This
module takes the other route: instead of asking a generic model to reason about
roles, it asks "which audited rows does this row resemble, and what did the
human decide about those?" -- supervision from real labels rather than prompt
wording.

ADVISORY ONLY. Nothing here changes a classification. It produces a predicted
label + confidence so a caller can FLAG disagreement with the rule engine.
Every proposal in this project that tried to auto-override on a signal that
could not separate the classes has regressed correct rows; kNN is not exempt.

OFFLINE: embeddings come from the vendored intfloat/multilingual-e5-small only.
No network at any point. build_gold_embedding_store() caches vectors to
.ml_cache/*.npz keyed by a hash of the input text, and reloads with
allow_pickle=False.

MEASURED RESULT (2026-07-21, 158 audited rows) — NOT wired into the pipeline:

    leave-one-out accuracy   51.9%  (k=5)
    majority-class baseline  32.9%
    k sweep                  44.9 / 48.7 / 51.9 / 50.0 / 52.5%  (k=1/3/5/10/20)
    rule engine, same rows   98.4%  (127/129 audited-correct)

It beats the trivial baseline by ~19 points, so the signal is real -- but it is
nowhere near the rule engine, so it can neither classify nor usefully flag
disagreement (at ~48% error it would contest half the corpus).

Diagnosis: this embeds the WHOLE request body, and e5 similarity is dominated
by the program's SUBJECT (arts / health / environment / housing) rather than by
who is served. Nearest neighbours come back topically similar but ethnically
unrelated. The served-population signal is a few words inside a long text.

The principled next step is span-context kNN -- embed the local window around
each identity mention, since the mention (not the row) is the unit the resolver
actually decides on. That needs span-level labels, which would have to be
derived from only 29 error rows; with n that small, overfitting is close to
guaranteed. Revisit once the 2023/24 sheets are audited and the labelled set is
several times larger.

Evaluate (leave-one-out over the audited rows):
    .venv/Scripts/python.exe Engine_1_and_2/Semantic_Engine/knn_gold.py
"""

GOLD_COLS = ["Ethnic 1 - FR6", "Ethnic 2 - FR7", "Ethnic 3 - FR8"]
AN_COL = "Classification Accuracy (Corrected in Different Areas)"
ID_COL = "SF_18_ID_Funding_Request__c"
DEFAULT_K = 5


def assert_offline():
    """Fail loudly rather than silently reaching for the network."""
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(var) != "1":
            raise RuntimeError(f"{var} is not set — refusing to run (offline-only module)")
    require_vendor(ENCODER_DIR, "intfloat/multilingual-e5-small")


def load_audited(gold_path):
    """Audited rows only (column AN non-blank), with gold label + verdict."""
    import pandas as pd
    try:
        df = pd.read_excel(gold_path, sheet_name="Discretionary Funding Requests", dtype=str)
    except PermissionError:
        tmp = Path(tempfile.gettempdir()) / f"_locked_{Path(gold_path).name}"
        shutil.copy2(gold_path, tmp)
        try:
            df = pd.read_excel(tmp, sheet_name="Discretionary Funding Requests", dtype=str)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
    df = df.fillna("")
    rows = []
    for _, r in df.iterrows():
        an = str(r.get(AN_COL, "") or "").strip()
        if not an:
            continue
        d = dict(r)
        d["id"] = str(r.get(ID_COL, "") or "").strip()
        d["gold_l1"] = str(r.get(GOLD_COLS[0], "") or "").strip()
        d["verdict"] = an.split()[0].lower()
        rows.append(d)
    return rows


def predict(query_vec, store, labels, k=DEFAULT_K, exclude_id=None):
    """Similarity-weighted vote over the k nearest audited rows.

    exclude_id drops the query's own entry -- mandatory when scoring a row that
    is itself in the store, otherwise it matches itself at similarity 1.0 and
    the evaluation reports accuracy it does not have.

    Returns (predicted_label, confidence, [(id, similarity, label), ...]) where
    confidence is the winning label's share of total similarity mass (0..1).
    """
    vecs = store["body_vecs"]
    if len(vecs) == 0:
        return "", 0.0, []
    sims = vecs @ query_vec.astype(np.float32)      # vectors are L2-normalised => cosine
    order = np.argsort(-sims)

    neighbours = []
    for i in order:
        gid = store["ids"][i]
        if exclude_id is not None and gid == exclude_id:
            continue
        neighbours.append((gid, float(sims[i]), labels.get(gid, "")))
        if len(neighbours) >= k:
            break

    weights = defaultdict(float)
    for gid, sim, lab in neighbours:
        if lab:
            weights[lab] += max(sim, 0.0)
    if not weights:
        return "", 0.0, neighbours
    total = sum(weights.values())
    best = max(weights, key=weights.get)
    return best, (weights[best] / total if total else 0.0), neighbours


def build(rows, force=False):
    """Embedding store over the audited rows + an id->gold-label map."""
    store = build_gold_embedding_store(rows, force=force)
    labels = {r["id"]: r["gold_l1"] for r in rows}
    return store, labels


def _evaluate(k=DEFAULT_K):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import bootstrap
    sys.path.insert(0, str(bootstrap.PROJECT_ROOT / "Engine_1_and_2" / "Pipeline"))
    import ethnic_taggerv3 as et

    assert_offline()
    gold_path = bootstrap.PROJECT_ROOT / "Taxonomy" / "AUDITED_FR_GOLD.xlsx"
    rows = load_audited(gold_path)
    store, labels = build(rows)
    print(f"audited rows: {len(rows)}  (embeddings cached offline)")

    # Trivial baseline: always guess the most common gold label. kNN has to beat
    # this to be worth anything -- the label distribution is heavily skewed.
    counts = defaultdict(int)
    for r in rows:
        counts[r["gold_l1"]] += 1
    majority = max(counts, key=counts.get)
    base_acc = counts[majority] / len(rows)

    hits = 0
    by_verdict = {"correct": [0, 0], "wrong": [0, 0]}
    for r in rows:
        body, _name = et.get_body_and_name_texts(r)
        qv = embed(body, kind="query")
        pred, conf, _nb = predict(qv, store, labels, k=k, exclude_id=r["id"])
        ok = (pred == r["gold_l1"])
        hits += ok
        slot = by_verdict.get(r["verdict"])
        if slot:
            slot[0] += ok
            slot[1] += 1

    print(f"\nleave-one-out accuracy (k={k}): {hits}/{len(rows)} = {hits/len(rows):.1%}")
    print(f"majority-class baseline          : {base_acc:.1%}  ('{majority[:40]}')")
    for v, (ok, n) in by_verdict.items():
        if n:
            print(f"  rows you marked {v:8}: {ok}/{n} = {ok/n:.1%}")
    print("\nkNN must clear the baseline by a wide margin to be worth wiring in.")


if __name__ == "__main__":
    _evaluate()
