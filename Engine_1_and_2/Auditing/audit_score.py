"""
audit_score.py
--------------
Gold-standard audit scorer — two modes:

    python audit_score.py --init
        Creates Taxonomy/audit_gold.xlsx: one row per data row,
        pre-filled with live engine output and blank correction columns
        ready for the auditor to fill in.  Rows missing SF_18_ID are
        skipped and counted.

    Workflow: fill in the correction columns, then save the completed file
    as  Taxonomy/audit_gold_audited.xlsx  (same folder) before scoring.

    python audit_score.py
        Loads Taxonomy/audit_gold_audited.xlsx, re-runs classifiers on live
        data, joins on stable_id, and over the audited (non-blank) rows
        computes precision/recall/F1 per category.  Writes
        Data Sheets/audit_scorecard.xlsx.

Stable ID: SF_18_ID_Funding_Request__c
Any row missing this value is skipped; a count is printed.

Correction columns the auditor fills (blank = not yet audited → skipped):
    Correct Ethnic 1 | Correct Gender Id | Correct Sexual Id
    Ethnic Flag OK?  | Gender Flag OK?   | Sexual Flag OK?   | Notes

Flag OK? accepts: Yes/Y/True/1 (flag is appropriate) or No/N/False/0 (not).
"""

import sys
import re
import unicodedata
import argparse
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap 

import pandas as pd

import ethnic_taggerv3 as et
from classify_pipeline import classify_row as pipeline_classify_row
import Gender_SexID as gs
import audit_evidence as ae
from constants import GENERAL_POP as ETHNIC_GENERAL_POP
from gender_constants import GENDER_GENERAL_POP, SEXUAL_GENERAL_POP

# ---------------------------------------------------------------------------
# Column name constants
# ---------------------------------------------------------------------------
STABLE_ID_COL = "SF_18_ID_Funding_Request__c"

GOLD_FILE          = "audit_gold.xlsx"
AUDITED_GOLD_FILE  = "audit_gold_audited.xlsx"
SCORECARD_FILE     = "audit_scorecard.xlsx"

_GENERAL_POP_VARIANTS = {ETHNIC_GENERAL_POP, GENDER_GENERAL_POP, SEXUAL_GENERAL_POP}


def _canon(label):
    """Fold axis-specific 'General Population (No specific ...)' dropdown
    variants to one common label, so a gender/sexual value mistakenly
    pasted into the ethnic column doesn't register as a real disagreement."""
    if pd.isna(label):
        label = ""
    label = str(label).strip()
    return "General Population" if label in _GENERAL_POP_VARIANTS else label


def _norm(s):
    """Loose taxonomy-label normalizer for the depth-fair ethnic comparison:
    folds accents/case/punctuation and taxonomy-string noise ("Origins",
    "(India)", "and Middle Eastern") that varies between gold and engine
    without being a real disagreement."""
    if s is None:
        s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)                     # drop "(India)"
    s = s.replace(", not otherwise specified", "")
    s = re.sub(r"\borigins?\b", "", s)                # drop the word "origins"
    s = re.sub(r"\band middle eastern\b", "", s)       # gold omits this in some L2 labels
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return "general" if s.startswith("general population") else s


def _eth_deepest(e1, e2, e3):
    """The most specific non-empty ethnic level the engine assigned."""
    for x in (e3, e2, e1):
        if x and str(x).strip():
            return x
    return e1

# Engine output columns (stored in both gold template and re-derived at score time)
ENG_ETHNIC1     = "Ethnic 1 (engine)"
ENG_ETHNIC2     = "Ethnic 2 (engine)"
ENG_ETHNIC3     = "Ethnic 3 (engine)"
ENG_GENDER      = "Gender Id (engine)"
ENG_SEXUAL      = "Sexual Id (engine)"
ENG_ETHNIC_FLAG = "Classification Flag (engine)"
ENG_GENDER_FLAG = "Gender Flag (engine)"
ENG_SEXUAL_FLAG = "Sexual Flag (engine)"

# Auditor correction columns
CORRECT_ETHNIC1 = "Correct Ethnic 1"
CORRECT_GENDER  = "Correct Gender Id"
CORRECT_SEXUAL  = "Correct Sexual Id"
ETHNIC_FLAG_OK  = "Ethnic Flag OK?"
GENDER_FLAG_OK  = "Gender Flag OK?"
SEXUAL_FLAG_OK  = "Sexual Flag OK?"
NOTES_COL       = "Notes"

# Evidence columns (engine_df only → no suffix after merge)
COL_ETH_EV  = "Ethnic Evidence"
COL_GEN_EV  = "Gender Evidence"
COL_SEX_EV  = "Sexual Evidence"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_inputs():
    taxonomy_fp = bootstrap.PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx"
    funding_fp  = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"
    tax_df  = pd.read_excel(taxonomy_fp, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_fp,  sheet_name=et.DATA_SHEET,     dtype=str)
    return tax_df, data_df


def _run_classifiers(data_df, taxonomy_entries):
    """Classify every row that has a stable_id. Returns (DataFrame, skipped_count)."""
    rows = []
    skipped = 0
    for _, row in data_df.iterrows():
        sid = row.get(STABLE_ID_COL, "")
        if pd.isna(sid) or not str(sid).strip():
            skipped += 1
            continue
        e1, e2, e3, eflag = pipeline_classify_row(row, taxonomy_entries)
        g_label, g_flag   = gs.classify_gender(row)
        s_label, s_flag   = gs.classify_sexual(row)
        rows.append({
            STABLE_ID_COL:    str(sid).strip(),
            "Funding Request Name": str(row.get("Funding Request Name", "") or ""),
            ENG_ETHNIC1:      e1,
            ENG_ETHNIC2:      e2,
            ENG_ETHNIC3:      e3,
            ENG_GENDER:       g_label,
            ENG_SEXUAL:       s_label,
            ENG_ETHNIC_FLAG:  eflag,
            ENG_GENDER_FLAG:  g_flag,
            ENG_SEXUAL_FLAG:  s_flag,
            COL_ETH_EV:       ae.ethnic_evidence(row, taxonomy_entries),
            COL_GEN_EV:       ae.gender_evidence(row),
            COL_SEX_EV:       ae.sexual_evidence(row),
        })
    return pd.DataFrame(rows), skipped


def _parse_ok(val):
    """Convert an auditor 'Flag OK?' cell to True/False/None (None = not reviewed)."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    v = str(val).strip().lower()
    if v in ("yes", "y", "true", "1", "ok"):
        return True
    if v in ("no", "n", "false", "0"):
        return False
    return None


def _classification_metrics(y_true, y_pred):
    """Accuracy + per-class precision/recall/F1 over two aligned lists."""
    if not y_true:
        return {"accuracy": None, "per_class": {}}
    correct  = sum(t == p for t, p in zip(y_true, y_pred))
    accuracy = round(correct / len(y_true), 3)

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    for t, p in zip(y_true, y_pred):
        if t == p:
            tp[t] += 1
        else:
            fp[p] += 1
            fn[t]  += 1

    per_class = {}
    for c in sorted(set(y_true) | set(y_pred)):
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        rec  = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        per_class[c] = {
            "precision": round(prec, 3),
            "recall":    round(rec,  3),
            "f1":        round(f1,   3),
            "support":   tp[c] + fn[c],
        }
    return {"accuracy": accuracy, "per_class": per_class}


def _flag_calibration(engine_flagged_list, ok_list):
    """
    Precision/recall of the engine's flagging behaviour.
    engine_flagged_list: list[bool]  — True when engine raised a non-empty flag
    ok_list: list[bool]              — True when auditor says the flag is appropriate
    """
    tp = fp = tn = fn = 0
    for flagged, ok in zip(engine_flagged_list, ok_list):
        if     flagged and     ok: tp += 1
        elif   flagged and not ok: fp += 1
        elif not flagged and   ok: tn += 1
        else:                      fn += 1
    prec = tp / (tp + fp) if (tp + fp) > 0 else None
    rec  = tp / (tp + fn) if (tp + fn) > 0 else None
    f1   = (2 * prec * rec / (prec + rec)
            if (prec is not None and rec is not None and (prec + rec) > 0)
            else None)
    return {
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "Precision": round(prec, 3) if prec is not None else None,
        "Recall":    round(rec,  3) if rec  is not None else None,
        "F1":        round(f1,   3) if f1   is not None else None,
        "Total Reviewed": tp + fp + tn + fn,
    }


# ---------------------------------------------------------------------------
# --init mode
# ---------------------------------------------------------------------------

def cmd_init():
    print("Loading taxonomy and funding requests...")
    tax_df, data_df = load_inputs()
    taxonomy_entries = et.build_taxonomy(tax_df)

    print("Running classifiers...")
    engine_df, skipped = _run_classifiers(data_df, taxonomy_entries)
    if skipped:
        print(f"  Skipped {skipped} rows missing '{STABLE_ID_COL}'.")

    # Build gold template: engine columns + blank correction columns
    gold_cols = [
        STABLE_ID_COL, "Funding Request Name",
        ENG_ETHNIC1, ENG_ETHNIC2, ENG_ETHNIC3,
        ENG_GENDER, ENG_SEXUAL,
        ENG_ETHNIC_FLAG, ENG_GENDER_FLAG, ENG_SEXUAL_FLAG,
        CORRECT_ETHNIC1, CORRECT_GENDER, CORRECT_SEXUAL,
        ETHNIC_FLAG_OK, GENDER_FLAG_OK, SEXUAL_FLAG_OK,
        NOTES_COL,
    ]
    gold_df = engine_df[[
        STABLE_ID_COL, "Funding Request Name",
        ENG_ETHNIC1, ENG_ETHNIC2, ENG_ETHNIC3,
        ENG_GENDER, ENG_SEXUAL,
        ENG_ETHNIC_FLAG, ENG_GENDER_FLAG, ENG_SEXUAL_FLAG,
    ]].copy()
    for col in [CORRECT_ETHNIC1, CORRECT_GENDER, CORRECT_SEXUAL,
                ETHNIC_FLAG_OK, GENDER_FLAG_OK, SEXUAL_FLAG_OK, NOTES_COL]:
        gold_df[col] = ""

    out_path = bootstrap.PROJECT_ROOT / "Taxonomy" / GOLD_FILE
    gold_df.to_excel(out_path, index=False)
    print(f"Written {len(gold_df)} rows → {out_path}")
    print("\nFill in 'Correct *' and 'Flag OK?' columns for audited rows,")
    print(f"save the completed file as Taxonomy/{AUDITED_GOLD_FILE},")
    print("then run:  python audit_score.py")


# ---------------------------------------------------------------------------
# default (scorer) mode
# ---------------------------------------------------------------------------

def cmd_score():
    gold_path = bootstrap.PROJECT_ROOT / "Taxonomy" / AUDITED_GOLD_FILE
    if not gold_path.exists():
        print(f"ERROR: {gold_path} not found.")
        print("Run 'python audit_score.py --init' to create the template first.")
        sys.exit(1)

    print(f"Loading gold file: {gold_path}")
    gold_df = pd.read_excel(gold_path, dtype=str)

    print("Re-running classifiers on live data...")
    tax_df, data_df = load_inputs()
    taxonomy_entries = et.build_taxonomy(tax_df)
    engine_df, skipped = _run_classifiers(data_df, taxonomy_entries)
    if skipped:
        print(f"  Skipped {skipped} rows missing '{STABLE_ID_COL}'.")

    # Join on stable_id.
    # Columns that exist in BOTH gold_df and engine_df get _gold / _live suffixes.
    # Correction columns (only in gold_df) and evidence columns (only in engine_df)
    # keep their plain names.
    merged = gold_df.merge(
        engine_df, on=STABLE_ID_COL, how="inner", suffixes=("_gold", "_live")
    )
    print(f"Joined {len(merged)} rows on '{STABLE_ID_COL}'.")

    # Convenience: live engine column names after merge
    E1_L   = ENG_ETHNIC1     + "_live"
    E2_L   = ENG_ETHNIC2     + "_live"
    E3_L   = ENG_ETHNIC3     + "_live"
    EG_L   = ENG_GENDER      + "_live"
    ES_L   = ENG_SEXUAL      + "_live"
    EF_L   = ENG_ETHNIC_FLAG + "_live"
    GF_L   = ENG_GENDER_FLAG + "_live"
    SF_L   = ENG_SEXUAL_FLAG + "_live"

    # ------------------------------------------------------------------
    # Ethnic axis
    # ------------------------------------------------------------------
    eth_mask    = merged[CORRECT_ETHNIC1].notna() & (merged[CORRECT_ETHNIC1].str.strip() != "")
    eth_audited = merged[eth_mask]

    # Depth-fair comparison: gold collapses the answer into one "L1 - L2/L3"
    # string, while the engine reports Ethnic 1/2/3 separately. A row only
    # counts as wrong if the engine disagrees on BOTH the L1 group and the
    # deepest level it actually reached — matching at L2/L3 (e.g. gold
    # "Asian Origins - Indian" vs engine L1=Asian/L3=Indian) is correct.
    eth_true, eth_pred = [], []
    for gold_raw, e1, e2, e3 in zip(
        eth_audited[CORRECT_ETHNIC1].str.strip().tolist(),
        eth_audited[E1_L].tolist(), eth_audited[E2_L].tolist(), eth_audited[E3_L].tolist(),
    ):
        parts        = [p.strip() for p in gold_raw.split(" - ")]
        gold_l1      = parts[0]
        gold_deepest = parts[-1]
        eng_deepest  = _eth_deepest(e1, e2, e3)

        true_label = f"{_norm(gold_l1)} | {_norm(gold_deepest)}"
        match = (_norm(e1) == _norm(gold_l1)) and (_norm(eng_deepest) == _norm(gold_deepest))
        pred_label = true_label if match else f"{_norm(e1)} | {_norm(eng_deepest)}"

        eth_true.append(true_label)
        eth_pred.append(pred_label)

    eth_m = _classification_metrics(eth_true, eth_pred)

    eth_dis_mask = pd.Series(
        [t != p for t, p in zip(eth_true, eth_pred)], index=eth_audited.index
    )
    eth_dis = eth_audited[eth_dis_mask][[
        STABLE_ID_COL, "Funding Request Name_gold",
        E1_L, CORRECT_ETHNIC1, COL_ETH_EV, NOTES_COL,
    ]].rename(columns={
        "Funding Request Name_gold": "Funding Request Name",
        E1_L: "Engine Ethnic 1",
        COL_ETH_EV: "Ethnic Evidence",
    })

    # ------------------------------------------------------------------
    # Gender axis
    # ------------------------------------------------------------------
    gen_mask    = merged[CORRECT_GENDER].notna() & (merged[CORRECT_GENDER].str.strip() != "")
    gen_audited = merged[gen_mask]
    gen_true    = [_canon(v) for v in gen_audited[CORRECT_GENDER].str.strip().tolist()]
    gen_pred    = [_canon(v) for v in gen_audited[EG_L].tolist()]
    gen_m       = _classification_metrics(gen_true, gen_pred)

    gen_dis_mask = (gen_audited[CORRECT_GENDER].str.strip().map(_canon) != gen_audited[EG_L].map(_canon))
    gen_dis = gen_audited[gen_dis_mask][[
        STABLE_ID_COL, "Funding Request Name_gold",
        EG_L, CORRECT_GENDER, COL_GEN_EV, NOTES_COL,
    ]].rename(columns={
        "Funding Request Name_gold": "Funding Request Name",
        EG_L: "Engine Gender Id",
        COL_GEN_EV: "Gender Evidence",
    })

    # ------------------------------------------------------------------
    # Sexual axis
    # ------------------------------------------------------------------
    sex_mask    = merged[CORRECT_SEXUAL].notna() & (merged[CORRECT_SEXUAL].str.strip() != "")
    sex_audited = merged[sex_mask]
    sex_true    = [_canon(v) for v in sex_audited[CORRECT_SEXUAL].str.strip().tolist()]
    sex_pred    = [_canon(v) for v in sex_audited[ES_L].tolist()]
    sex_m       = _classification_metrics(sex_true, sex_pred)

    sex_dis_mask = (sex_audited[CORRECT_SEXUAL].str.strip().map(_canon) != sex_audited[ES_L].map(_canon))
    sex_dis = sex_audited[sex_dis_mask][[
        STABLE_ID_COL, "Funding Request Name_gold",
        ES_L, CORRECT_SEXUAL, COL_SEX_EV, NOTES_COL,
    ]].rename(columns={
        "Funding Request Name_gold": "Funding Request Name",
        ES_L: "Engine Sexual Id",
        COL_SEX_EV: "Sexual Evidence",
    })

    # ------------------------------------------------------------------
    # Flag calibration
    # ------------------------------------------------------------------
    def _cal(flag_live_col, ok_col):
        reviewed_mask = merged[ok_col].apply(_parse_ok).notna()
        r = merged[reviewed_mask]
        if r.empty:
            return None
        flagged = (r[flag_live_col].fillna("").str.strip() != "").tolist()
        ok_vals = r[ok_col].apply(_parse_ok).tolist()
        return _flag_calibration(flagged, ok_vals)

    eth_cal = _cal(EF_L, ETHNIC_FLAG_OK)
    gen_cal = _cal(GF_L, GENDER_FLAG_OK)
    sex_cal = _cal(SF_L, SEXUAL_FLAG_OK)

    # ------------------------------------------------------------------
    # Summary tab
    # ------------------------------------------------------------------
    summary_rows = []
    for axis, m, n in [
        ("Ethnic 1",  eth_m, len(eth_audited)),
        ("Gender Id", gen_m, len(gen_audited)),
        ("Sexual Id", sex_m, len(sex_audited)),
    ]:
        summary_rows.append({
            "Axis": axis, "Rows Audited": n,
            "Accuracy": m["accuracy"],
            "Precision": "", "Recall": "", "F1": "", "Support": "",
        })
        for cat, s in m.get("per_class", {}).items():
            summary_rows.append({
                "Axis": f"  → {cat}", "Rows Audited": "",
                "Accuracy": "",
                "Precision": s["precision"],
                "Recall":    s["recall"],
                "F1":        s["f1"],
                "Support":   s["support"],
            })
    summary_df = pd.DataFrame(summary_rows)

    # ------------------------------------------------------------------
    # Flag calibration tab
    # ------------------------------------------------------------------
    cal_rows = []
    for label, cal in [("Ethnic Flag", eth_cal), ("Gender Flag", gen_cal), ("Sexual Flag", sex_cal)]:
        if cal is None:
            cal_rows.append({"Flag Axis": label, "Note": "No reviewed rows"})
        else:
            cal_rows.append({"Flag Axis": label, **cal})
    cal_df = pd.DataFrame(cal_rows)

    # ------------------------------------------------------------------
    # Write scorecard
    # ------------------------------------------------------------------
    out_path = bootstrap.PROJECT_ROOT / "Data Sheets" / SCORECARD_FILE
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary",               index=False)
        eth_dis.to_excel(   writer, sheet_name="Ethnic Disagreements",  index=False)
        gen_dis.to_excel(   writer, sheet_name="Gender Disagreements",  index=False)
        sex_dis.to_excel(   writer, sheet_name="Sexual Disagreements",  index=False)
        cal_df.to_excel(    writer, sheet_name="Flag Calibration",      index=False)

    print(f"\nScorecard written → {out_path}")
    print(f"  Ethnic : {len(eth_audited):>4} rows audited, {len(eth_dis):>3} disagreements")
    print(f"  Gender : {len(gen_audited):>4} rows audited, {len(gen_dis):>3} disagreements")
    print(f"  Sexual : {len(sex_audited):>4} rows audited, {len(sex_dis):>3} disagreements")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Audit gold-standard scorer")
    parser.add_argument(
        "--init", action="store_true",
        help="Generate the audit_gold.xlsx template (does not score)",
    )
    args = parser.parse_args()
    if args.init:
        cmd_init()
    else:
        cmd_score()


if __name__ == "__main__":
    main()
