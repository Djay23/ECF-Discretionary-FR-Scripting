"""
generate_stakeholder_dashboard.py
---------------------------------
Stakeholder-facing presentation layer for the FR classification engine.

Unlike generate_review_report.py (an engineer-facing diagnostic workbook), this
builds a single self-contained HTML dashboard meant to be shown to stakeholders /
the board. It tells two clearly-separated stories:

  PART A — Equity lens ("who discretionary funding serves")
      Distribution of served populations across every classification axis, plus
      an intersectional (ethnic x gender) view.

  PART B — Operations lens ("engine QA / review burden")
      How many records were flagged, which flags dominate, the high- vs
      low-priority split (the reviewer-fatigue story), and engine-vs-human
      accuracy over the audited rows.

READ-ONLY: never runs the engine's write-back, never modifies FR testing.xlsx.

Two data-source modes (set MODE below):
  "gold"  (default) — the dataset's Final Review copy: engine output with the
                      reviewer's corrections already applied (what menu option 3
                      writes). Falls back to the gold snapshot in Taxonomy/ if a
                      dataset has no Final Review copy yet. Accuracy is reportable
                      straight from the file, so no live classification is needed.
  "live"            — the dataset's source workbook. Classifies every row live by
                      reusing the same per-row loop as generate_review_report.py,
                      and picks up the pending Sector / Affordable Housing (AH) /
                      Early Childhood Development (ECD) columns once they are
                      imported. Deferred until that import is done.

To run:
    $env:PYTHONIOENCODING="utf-8"; python Engine_1_and_2/Auditing/generate_stakeholder_dashboard.py

Output:
    Data Sheets/stakeholder_dashboard.html   (publish via the Artifact tool)
"""

import sys
import re
import html
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine_1_and_2
import bootstrap  # noqa: F401  (sets sys.path + UTF-8 stdout, defines PROJECT_ROOT)
import paths  # noqa: E402  (resolves the workspace -- may be outside PROJECT_ROOT)

import pandas as pd

from constants import GENERAL_POP as ETHNIC_GENERAL_POP
from gender_constants import GENDER_GENERAL_POP, SEXUAL_GENERAL_POP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODE = "gold"                      # "gold" | "live"
TOP_FLAGS = 12                     # rows in the top-flags table

GENERAL_VARIANTS = {ETHNIC_GENERAL_POP, GENDER_GENERAL_POP, SEXUAL_GENERAL_POP}
LOW_PRIORITY_PREFIX = "note (low priority)"

# --- Column names, shared by the gold and Final Review copies -------------------------------------
GOLD_ETHNIC1     = "Ethnic 1 - FR6"
GOLD_ETHNIC2     = "Ethnic 2 - FR7"
GOLD_ETHNIC3     = "Ethnic 3 - FR8"
GOLD_GENDER      = "Gender Id - FR9"
GOLD_SEXUAL      = "Sexual Id - FR10"
GOLD_ETHNIC_FLAG = "Classification Flag"
GOLD_GENDER_FLAG = "Gender Classification Flag"
GOLD_SEXUAL_FLAG = "Sexual Classification Flag"
GOLD_VERDICT     = "Classification Accuracy (Corrected in Different Areas)"
GOLD_SECTOR      = "Sector 1 - FR"   # primary sector; a request may name up to 4
GOLD_AH          = "AH - FR"         # Affordable Housing focus area (True/False)
GOLD_ECD         = "ECD - FR"        # Early Childhood Development focus area (True/False)

# Values that count as "yes" in the boolean AH/ECD focus-area columns.
TRUE_VALUES = {"true", "yes", "y", "1", "x"}

# Stand-in for "the human replaced this value". The workbook was corrected in
# place, so the pre-correction engine output is not stored anywhere except as
# prose inside the verdict ("... Formerly Indigenous"). accuracy() only needs a
# value that compares unequal, never the real former label.
CORRECTED_SENTINEL = "— corrected by reviewer —"


def parse_audit_verdict(text):
    """Parse one 'Classification Accuracy' cell into per-axis correctness.

    Returns None for an unaudited (blank) row, else a dict of
    {axis: True if the human marked that axis WRONG}.

    The column is free text written by a human, so this keys off which axis
    names appear inside a "Wrong ..." clause rather than assuming a fixed
    layout. Real forms present in the 2025 sheet:
        "Correct Ethnic, Gender and Sex, Focus"
        "Wrong Ethnic - Formerly Indigenous"
        "Wrong Ethnic - Formerly Multiple; Wrong Gender - Formerly General"
        "Wrong Ethnic and Gender - Formerly Other for ETHNIC, ..."   <- one clause, two axes
        "Wrong Gender - Formerly Women/girls"                        <- ethnic was fine
    Note the 4th form: a single "Wrong" clause naming two axes, which is why
    each axis is searched for independently instead of splitting on ';'.
    """
    s = str(text or "").strip()
    if not s:
        return None
    low = s.lower()
    if not low.startswith("wrong"):
        return {"ethnic": False, "gender": False, "sexual": False}
    # Scope each axis test to text following a "wrong" token so that a trailing
    # explanatory clause cannot mark an axis the reviewer did not fault.
    tail = low[low.find("wrong"):]
    return {
        "ethnic": bool(re.search(r"wrong[^.;]*ethnic", tail)),
        "gender": bool(re.search(r"wrong[^.;]*gender", tail)),
        "sexual": bool(re.search(r"wrong[^.;]*sex\b|wrong[^.;]*sexual", tail)),
    }

# Canonical normalized record columns produced by load_records().
COL = dict(
    name="name", ethnic1="ethnic1", ethnic2="ethnic2", ethnic3="ethnic3",
    gender="gender", sexual="sexual",
    ethnic_flag="ethnic_flag", gender_flag="gender_flag", sexual_flag="sexual_flag",
    correct_ethnic="correct_ethnic", correct_gender="correct_gender",
    correct_sexual="correct_sexual",
    sector="sector", ah="affordable_housing", ecd="early_childhood_development",
)

# Axis panels rendered in Part A. Extra axes (sector) light up automatically when
# the normalized column is present and non-empty; otherwise they are skipped.
EQUITY_AXES = [
    ("Ethnic & cultural origin", COL["ethnic1"], ETHNIC_GENERAL_POP),
    ("Gender identity",          COL["gender"],  GENDER_GENERAL_POP),
    ("Sexual identity",          COL["sexual"],  SEXUAL_GENERAL_POP),
    ("Sector",                   COL["sector"],  None),
]

FLAG_AXES = [
    ("Ethnic", COL["ethnic_flag"]),
    ("Gender", COL["gender_flag"]),
    ("Sexual", COL["sexual_flag"]),
]

ACCURACY_AXES = [
    ("Ethnic", COL["ethnic1"], COL["correct_ethnic"]),
    ("Gender", COL["gender"],  COL["correct_gender"]),
    ("Sexual", COL["sexual"],  COL["correct_sexual"]),
]


# ---------------------------------------------------------------------------
# Normalization helpers (depth-fair accuracy, borrowed from audit_score.py)
# ---------------------------------------------------------------------------
def canon(label):
    """Fold the three axis-specific 'General Population (...)' dropdown variants
    to one common 'General Population' token."""
    if pd.isna(label):
        label = ""
    label = str(label).strip()
    return "General Population" if label in GENERAL_VARIANTS else label


def norm(s):
    """Loose taxonomy-label normalizer: folds accents/case/punctuation and
    taxonomy-string noise ('Origins', '(India)', 'and Middle Eastern') that
    varies between gold and engine without being a real disagreement."""
    if s is None:
        s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace(", not otherwise specified", "")
    s = re.sub(r"\borigins?\b", "", s)
    s = re.sub(r"\band middle eastern\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return "general" if s.startswith("general population") else s


def is_general(label):
    return canon(label) == "General Population"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _find_col(df, *needles):
    """First column whose lowercased name contains all needles (space-joined)."""
    for c in df.columns:
        low = str(c).lower()
        if all(n in low for n in needles):
            return c
    return None


def load_records(ds):
    """Return (records_df with canonical columns, meta dict)."""
    if MODE == "gold":
        return _load_gold(ds)
    if MODE == "live":
        return _load_live(ds)
    raise ValueError(f"Unknown MODE {MODE!r}")


def _reviewed_source(ds):
    """The workbook that represents the FINISHED state of a dataset: engine
    classification with the reviewer's corrections applied on top.

    That is the Final Review copy -- the file apply_review_corrections.py
    writes into (menu option 3). The gold copy in Taxonomy/ is the audited
    snapshot BEFORE those corrections, so reporting from it understates the
    work: at the time of writing the 2025 Final Review copy carried 18
    corrected classification cells the gold copy did not, and 2023_24 carried
    23. Gold is still the fallback for a dataset whose corrections have not
    been applied yet."""
    fr = getattr(ds, "final_review_file", None)
    if fr is not None and fr.exists():
        return fr, "Final Review (corrections applied)"
    if ds.gold_file is not None:
        return ds.gold_file, "gold snapshot (no Final Review copy yet)"
    return None, None


def _load_gold(ds):
    fp, which = _reviewed_source(ds)
    if fp is None:
        raise SystemExit(
            f"Dataset '{ds.name}' has neither a Final Review copy nor a gold "
            f"file; MODE=\"gold\" is not available for this dataset. "
            f"Use MODE=\"live\" instead."
        )
    print(f"[dashboard] reading {which}: {fp.name}")
    df = pd.read_excel(fp, dtype=str).fillna("")

    # Flag columns are recomputed LIVE from the current engine so flags removed
    # from the engine don't resurface from the gold's stored snapshot. The
    # classification/accuracy columns below still come from the gold (human-
    # corrected in place).
    import ethnic_taggerv3 as _et
    from classify_pipeline import classify_row as _classify_row
    import Gender_SexID as _gs
    _entries = _et.build_taxonomy(
        pd.read_excel(ds.taxonomy_file, sheet_name=_et.TAXONOMY_SHEET, dtype=str))
    live_eflag, live_gflag, live_sflag = [], [], []
    for _, r in df.iterrows():
        live_eflag.append(_classify_row(r, _entries)[3])
        live_gflag.append(_gs.classify_gender(r)[1])
        live_sflag.append(_gs.classify_sexual(r)[1])

    # Column names below are AUDITED_FR_GOLD.xlsx's. The previous mapping used
    # the older audit_gold_audited.xlsx schema ("Ethnic 1 (engine)",
    # "Classification Flag (engine)", "Correct Ethnic 1"), none of which exist
    # here -- and because df.get() returns a default instead of raising, every
    # label and flag silently came back blank. The dashboard rendered 448
    # records with 0 flags and empty equity charts rather than failing.
    missing = [c for c in (GOLD_ETHNIC1, GOLD_GENDER, GOLD_ETHNIC_FLAG)
               if c not in df.columns]
    if missing:
        raise SystemExit(
            f"{fp.name} is missing expected column(s): {missing}\n"
            f"Found: {[c for c in df.columns if not str(c).startswith('Unnamed')]}"
        )

    if GOLD_VERDICT not in df.columns:
        # A dataset reviewed for the first time has no human verdicts yet --
        # that column only appears once somebody has audited rows. Treat it as
        # empty rather than refusing to build: the equity and flag lenses come
        # from the classification columns and are perfectly valid without it,
        # and accuracy() already reports "0 of N audited" when there are none.
        df = df.copy()
        df[GOLD_VERDICT] = ""

    verdicts = df[GOLD_VERDICT].map(parse_audit_verdict)

    def _correct(axis_key, value_col):
        """accuracy() compares engine value against a 'correct' value and skips
        blank ones. In this workbook the human corrected IN PLACE, so the label
        columns ARE the gold -- comparing them to themselves would report 100%.
        The real signal is the audit verdict, so emit a value that agrees when
        the human marked the axis correct and deliberately disagrees when they
        marked it wrong. Unaudited rows stay blank and are excluded."""
        out = []
        for val, v in zip(df[value_col], verdicts):
            if v is None:
                out.append("")
            elif v.get(axis_key):
                out.append(CORRECTED_SENTINEL)
            else:
                out.append(val)
        return out

    out = pd.DataFrame({
        COL["name"]:           df.get("Funding Request Name", ""),
        COL["ethnic1"]:        df[GOLD_ETHNIC1],
        COL["ethnic2"]:        df.get(GOLD_ETHNIC2, ""),
        COL["ethnic3"]:        df.get(GOLD_ETHNIC3, ""),
        COL["gender"]:         df[GOLD_GENDER],
        COL["sexual"]:         df.get(GOLD_SEXUAL, ""),
        COL["ethnic_flag"]:    live_eflag,
        COL["gender_flag"]:    live_gflag,
        COL["sexual_flag"]:    live_sflag,
        COL["correct_ethnic"]: _correct("ethnic", GOLD_ETHNIC1),
        COL["correct_gender"]: _correct("gender", GOLD_GENDER),
        COL["correct_sexual"]: _correct("sexual", GOLD_SEXUAL),
        # Sector (primary) and the two ECF focus areas were hand-classified and
        # live in the gold workbook -- carry them through so Part A renders them
        # instead of the "pending import" placeholder.
        COL["sector"]:         df.get(GOLD_SECTOR, ""),
        COL["ah"]:             df.get(GOLD_AH, ""),
        COL["ecd"]:            df.get(GOLD_ECD, ""),
    })
    n_aud = sum(1 for v in verdicts if v is not None)
    meta = dict(
        source=f"Audited gold set ({fp.name}, {n_aud} of {len(df)} rows audited)",
        mode="gold",
    )
    return out.fillna(""), meta


def _load_live(ds):
    """Classify the active dataset's raw workbook live, reusing the engine
    pipeline. Also picks up Sector / AH / ECD columns when present."""
    import ethnic_taggerv3 as et
    from classify_pipeline import classify_row as pipeline_classify_row
    import Gender_SexID as gs

    tax_fp = ds.taxonomy_file
    data_fp = ds.raw_file
    tax_df = pd.read_excel(tax_fp, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(data_fp, sheet_name=et.DATA_SHEET, dtype=str).fillna("")
    taxonomy_entries = et.build_taxonomy(tax_df)

    sector_col = _find_col(data_df, "sector")
    ah_col = _find_col(data_df, "affordable", "housing") or _find_col(data_df, "affordable housing")
    ecd_col = (_find_col(data_df, "early", "childhood")
               or _find_col(data_df, "ecd"))

    rows = []
    for _, row in data_df.iterrows():
        e1, e2, e3, eflag = pipeline_classify_row(row, taxonomy_entries)
        g_label, g_flag = gs.classify_gender(row)
        s_label, s_flag = gs.classify_sexual(row)
        rows.append({
            COL["name"]: row.get("Funding Request Name", ""),
            COL["ethnic1"]: e1, COL["ethnic2"]: e2, COL["ethnic3"]: e3,
            COL["gender"]: g_label, COL["sexual"]: s_label,
            COL["ethnic_flag"]: eflag, COL["gender_flag"]: g_flag,
            COL["sexual_flag"]: s_flag,
            COL["sector"]: row.get(sector_col, "") if sector_col else "",
            COL["ah"]: row.get(ah_col, "") if ah_col else "",
            COL["ecd"]: row.get(ecd_col, "") if ecd_col else "",
        })
    meta = dict(source=f"Live engine output ({data_fp.name})", mode="live")
    return pd.DataFrame(rows).fillna(""), meta


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def distribution(df, col, total):
    """[(label, count, pct, is_general)] ordered by count desc, for a label column."""
    if col not in df.columns:
        return []
    series = df[col].map(lambda x: str(x).strip()).replace("", pd.NA).dropna()
    if series.empty:
        return []
    rows = []
    for label, count in series.value_counts().items():
        rows.append((str(label), int(count), 100.0 * count / total, is_general(label)))
    return rows


def split_flags(cell):
    """A flag cell -> list of individual flag strings.

    The engine joins distinct flags with '; ' (resolver.build_output), but some
    individual flags contain an internal '; ' (e.g. "...broader population;
    confirm the classification isn't narrower..."). A naive split on ';' shreds
    those into fragments ("verify", "confirm ...") that then count as separate
    high-priority items and render as junk rows. Every catalogued flag starts
    with an uppercase letter or the 'Note (low priority):' prefix, while these
    internal continuations start lowercase — so re-attach any lowercase-leading
    segment to the flag it belongs to."""
    parts = []
    for p in str(cell).split(";"):
        p = p.strip()
        if not p:
            continue
        if parts and p[:1].islower():
            parts[-1] = parts[-1] + "; " + p
        else:
            parts.append(p)
    return parts


def flag_tier(flag):
    return "low" if flag.lower().startswith(LOW_PRIORITY_PREFIX) else "high"


def flag_stats(df, total):
    """Overall + per-axis flag tallies and priority split."""
    counter = Counter()
    axis_counter = {name: Counter() for name, _ in FLAG_AXES}
    high = low = 0
    rows_any = 0
    axis_rows_flagged = {name: 0 for name, _ in FLAG_AXES}

    for _, row in df.iterrows():
        row_has_flag = False
        for name, col in FLAG_AXES:
            if col not in df.columns:
                continue
            parts = split_flags(row[col])
            if parts:
                axis_rows_flagged[name] += 1
                row_has_flag = True
            for p in parts:
                counter[p] += 1
                axis_counter[name][p] += 1
                if flag_tier(p) == "low":
                    low += 1
                else:
                    high += 1
        if row_has_flag:
            rows_any += 1

    return dict(
        counter=counter, axis_counter=axis_counter,
        high=high, low=low, total_instances=high + low,
        rows_any=rows_any, rows_any_pct=100.0 * rows_any / total,
        axis_rows_flagged=axis_rows_flagged,
    )


def crosstab(df, row_col, col_col):
    """Counts of (row_label x col_label) over rows where BOTH axes are non-General.
    Returns (row_labels, col_labels, matrix[r][c], max_cell)."""
    if row_col not in df.columns or col_col not in df.columns:
        return [], [], [], 0
    mat = Counter()
    for _, r in df.iterrows():
        rv, cv = str(r[row_col]).strip(), str(r[col_col]).strip()
        if not rv or not cv or is_general(rv) or is_general(cv):
            continue
        mat[(rv, cv)] += 1
    if not mat:
        return [], [], [], 0
    row_labels = sorted({k[0] for k in mat}, key=lambda x: -sum(v for k, v in mat.items() if k[0] == x))
    col_labels = sorted({k[1] for k in mat}, key=lambda x: -sum(v for k, v in mat.items() if k[1] == x))
    matrix = [[mat.get((rl, cl), 0) for cl in col_labels] for rl in row_labels]
    return row_labels, col_labels, matrix, max(mat.values())


def accuracy(df):
    """[(axis, audited_n, agree_n, pct)] over rows with a filled Correct value."""
    out = []
    for name, eng_col, cor_col in ACCURACY_AXES:
        if eng_col not in df.columns or cor_col not in df.columns:
            out.append((name, 0, 0, None))
            continue
        sub = df[df[cor_col].map(lambda x: str(x).strip() != "")]
        n = len(sub)
        if n == 0:
            out.append((name, 0, 0, None))
            continue
        agree = 0
        for _, r in sub.iterrows():
            eng, cor = r[eng_col], r[cor_col]
            if canon(eng) == "General Population" or canon(cor) == "General Population":
                ok = canon(eng) == canon(cor)
            else:
                ok = norm(eng) == norm(cor)
            agree += int(ok)
        out.append((name, n, agree, 100.0 * agree / n))
    return out


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s))


def fmt_pct(p):
    return f"{p:.1f}%"


# Concise display labels for the (verbose) canonical classification strings.
PRETTY = {
    "Multiple Ethnic and Cultural Origins": "Multiple origins",
    "Other Ethnic and Cultural Origins": "Other origins",
    "North American Indigenous Origins": "Indigenous (N. American)",
    "Women and/or girls": "Women / girls",
    "Men and/or boys": "Men / boys",
    "Multiple gender identities": "Multiple gender identities",
    "Other (Agender, Gender fluid, Gender neutral, Genderqueer, Non-binary, Transgender)":
        "Other gender-diverse",
}


def pretty(label):
    """Short, human display label; folds the three verbose 'General Population'
    variants to one and trims taxonomy boilerplate."""
    label = str(label).strip()
    if is_general(label):
        return "General population"
    if label in PRETTY:
        return PRETTY[label]
    return re.sub(r"\s+Origins$", "", label)


# Very short labels for tight heatmap headers (full text stays in the tooltip).
HEAT_SHORT = {
    "Women and/or girls": "Women",
    "Men and/or boys": "Men",
    "Multiple gender identities": "Multiple",
    "Other (Agender, Gender fluid, Gender neutral, Genderqueer, Non-binary, Transgender)": "Other",
    "Two-Spirit": "2-Spirit",
}


def heat_label(label):
    return HEAT_SHORT.get(str(label).strip(), pretty(label))


# Short labels for the (long) engine flag strings, matched by substring.
FLAG_SHORT = [
    ("general indigenous term matched", "General Indigenous term, no specific nation named"),
    ("regional phrase matched", "Regional phrase, not a specific country (e.g. North African)"),
    ("curated lookup list", "Classified from org name only, no text signal"),
    ("known dual-identity phrase", "Dual-identity phrase (e.g. Afro-Caribbean)"),
    ("broad, non-specific identity term", "Broad identity term, no specific group named"),
    ("potential ethnocultural organization", "Possible ethnocultural org name"),
    ("aspirational", "Aspirational / future language"),
    ("equity/diversity buzzword", "Equity/diversity buzzword alongside a real signal"),
    ("multiple distinct groups", "Multiple distinct groups detected"),
    ("appears near the matched group", "Named group may be one example within a broader population"),
    ("bipoc", "BIPOC signal"),
    ("consulted-party", "Consulted-party (expert/advisor) mention"),
    ("negation word", "Term appears near a negation word"),
    ("umbrella term (black)", "Umbrella 'Black' alongside a specific group"),
    ("no paired ethnic signal", "Ambiguous equity term, no ethnic signal"),
    ("language accommodation", "French treated as language accommodation"),
    ("2slgbtqia+ umbrella acronym", "Gender inferred from 2SLGBTQIA+ acronym"),
    ("gender-identity term", "2SLGBTQIA+ inferred from a gender term"),
    ("organization name (silent body)", "Classified from organization name"),
    ("cultural association", "'Cultural Association' detected"),
    ("hindu", "'Hindu' — religion vs. ethnicity"),
    ("indigenous umbrella term", "Indigenous umbrella + specific sub-group"),
    ("indigenous topic/partnership", "Indigenous topic/partnership mention"),
    ("multiple:", "Multiple gender identities"),
]


def short_flag(flag):
    low = flag.lower()
    for needle, label in FLAG_SHORT:
        if needle in low:
            return label
    # Fallback: trim the "Note (low priority): " prefix and clip.
    trimmed = re.sub(r"(?i)^note \(low priority\):\s*", "", flag)
    return (trimmed[:58] + "…") if len(trimmed) > 60 else trimmed


def bar_list(rows, total, max_count):
    """Horizontal labelled bars for a distribution: [(label,count,pct,is_general)]."""
    out = ['<div class="bars">']
    for label, count, pct, general in rows:
        w = max(1.5, 100.0 * count / max_count)
        cls = "bar-fill muted" if general else "bar-fill"
        out.append(
            f'<div class="bar-row">'
            f'<div class="bar-label" title="{esc(label)}">{esc(pretty(label))}</div>'
            f'<div class="bar-track"><div class="{cls}" style="width:{w:.2f}%"></div>'
            f'<span class="bar-val">{count:,} · {fmt_pct(pct)}</span></div>'
            f'</div>'
        )
    out.append("</div>")
    return "".join(out)


def count_true(df, col):
    """How many rows have a truthy value in a boolean focus-area column."""
    if col not in df.columns:
        return 0
    return int(df[col].map(lambda x: str(x).strip().lower() in TRUE_VALUES).sum())


def focus_area_card(df, total):
    """Part A panel for the two ECF focus areas (Affordable Housing, Early
    Childhood Development). These are yes/no flags, not populations, so they get
    a compact count-of-yes panel rather than a distribution of groups."""
    areas = [
        ("Affordable Housing", COL["ah"]),
        ("Early Childhood Development", COL["ecd"]),
    ]
    tiles = []
    for name, col in areas:
        if col not in df.columns:
            continue
        n = count_true(df, col)
        pct = (100.0 * n / total) if total else 0.0
        tiles.append(
            f'<div class="acc"><div class="acc-val">{n:,}</div>'
            f'<div class="acc-label">{esc(name)}</div>'
            f'<div class="acc-sub">{fmt_pct(pct)} of {total:,} requests</div></div>'
        )
    if not tiles:
        return ""
    return (
        '<div class="card" style="grid-column:1/-1;"><h3>ECF focus areas</h3>'
        '<div class="sub">Requests hand-classified as advancing a priority focus area. '
        'A request can fall under both, neither, or one.</div>'
        f'<div class="acc-row">{"".join(tiles)}</div></div>'
    )


def kpi_tile(value, label, sub="", tone=""):
    tone_cls = f" tile-{tone}" if tone else ""
    sub_html = f'<div class="tile-sub">{esc(sub)}</div>' if sub else ""
    return (f'<div class="tile{tone_cls}"><div class="tile-value">{value}</div>'
            f'<div class="tile-label">{esc(label)}</div>{sub_html}</div>')


def heatmap(row_labels, col_labels, matrix, max_cell):
    if not matrix:
        return '<p class="empty">No rows carry signals on both axes.</p>'
    ncol = len(col_labels)
    out = [f'<div class="heat" style="grid-template-columns: minmax(96px,1.2fr) repeat({ncol}, minmax(46px,1fr));">']
    out.append('<div class="heat-corner"></div>')
    for cl in col_labels:
        out.append(f'<div class="heat-colhead" title="{esc(cl)}">{esc(heat_label(cl))}</div>')
    for r, rl in enumerate(row_labels):
        out.append(f'<div class="heat-rowhead" title="{esc(rl)}">{esc(pretty(rl))}</div>')
        for c in range(ncol):
            v = matrix[r][c]
            alpha = 0.0 if max_cell == 0 else 0.12 + 0.85 * (v / max_cell)
            strong = alpha > 0.55
            style = "" if v == 0 else f'background:rgba(var(--accent-rgb),{alpha:.2f});'
            txt = "strong" if strong else ""
            cell = "" if v == 0 else str(v)
            out.append(f'<div class="heat-cell {txt}" style="{style}">{cell}</div>')
    out.append("</div>")
    return "".join(out)


def flag_table(fstats, total):
    counter = fstats["counter"]
    if not counter:
        return '<p class="empty">No flags raised.</p>'
    max_c = counter.most_common(1)[0][1]
    out = ['<table class="flag-table"><thead><tr>'
           '<th>Review flag</th><th>Priority</th><th class="num">Records</th>'
           '<th class="num">Share</th></tr></thead><tbody>']
    for flag, count in counter.most_common(TOP_FLAGS):
        tier = flag_tier(flag)
        chip = ('<span class="chip chip-high">High</span>' if tier == "high"
                else '<span class="chip chip-low">Low</span>')
        w = 100.0 * count / max_c
        pct = 100.0 * count / total
        out.append(
            f'<tr><td><div class="flag-name">{esc(short_flag(flag))}</div>'
            f'<div class="mini"><div class="mini-fill mini-{tier}" style="width:{w:.1f}%"></div></div></td>'
            f'<td>{chip}</td>'
            f'<td class="num">{count:,}</td>'
            f'<td class="num">{fmt_pct(pct)}</td></tr>'
        )
    out.append("</tbody></table>")
    return "".join(out)


def priority_split(fstats):
    hi, lo = fstats["high"], fstats["low"]
    tot = hi + lo or 1
    hi_w, lo_w = 100.0 * hi / tot, 100.0 * lo / tot
    return (
        '<div class="split">'
        f'<div class="split-bar"><div class="split-high" style="width:{hi_w:.1f}%"></div>'
        f'<div class="split-low" style="width:{lo_w:.1f}%"></div></div>'
        '<div class="split-legend">'
        f'<span><i class="dot dot-high"></i>High priority — {hi:,} ({fmt_pct(hi_w)})</span>'
        f'<span><i class="dot dot-low"></i>Low priority — {lo:,} ({fmt_pct(lo_w)})</span>'
        '</div></div>'
    )


CSS = """
:root{
  --plane:#f4f6f4; --surface:#ffffff; --ink:#14201c; --ink-2:#55625c;
  --muted:#8a938d; --grid:#e4e8e4; --border:rgba(20,32,28,.10);
  --accent:#0f7b6c; --accent-rgb:15,123,108; --accent-weak:#d7ece7;
  --attn:#b06a06; --attn-rgb:176,106,6; --muted-fill:#d5ddd8;
  --good:#0f7b3f;
}
@media (prefers-color-scheme:dark){
  :root{
    --plane:#0c110f; --surface:#151a17; --ink:#f1f5f2; --ink-2:#b7c1bb;
    --muted:#7f8a83; --grid:#262d29; --border:rgba(255,255,255,.10);
    --accent:#33b7a0; --accent-rgb:51,183,160; --accent-weak:#183029;
    --attn:#e0973a; --attn-rgb:224,151,58; --muted-fill:#333c37; --good:#4bbd7a;
  }
}
:root[data-theme="light"]{
  --plane:#f4f6f4; --surface:#ffffff; --ink:#14201c; --ink-2:#55625c;
  --muted:#8a938d; --grid:#e4e8e4; --border:rgba(20,32,28,.10);
  --accent:#0f7b6c; --accent-rgb:15,123,108; --accent-weak:#d7ece7;
  --attn:#b06a06; --attn-rgb:176,106,6; --muted-fill:#d5ddd8; --good:#0f7b3f;
}
:root[data-theme="dark"]{
  --plane:#0c110f; --surface:#151a17; --ink:#f1f5f2; --ink-2:#b7c1bb;
  --muted:#7f8a83; --grid:#262d29; --border:rgba(255,255,255,.10);
  --accent:#33b7a0; --accent-rgb:51,183,160; --accent-weak:#183029;
  --attn:#e0973a; --attn-rgb:224,151,58; --muted-fill:#333c37; --good:#4bbd7a;
}
*{box-sizing:border-box}
.wrap{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);
  background:var(--plane);margin:0;padding:32px 20px 64px;line-height:1.5;
  min-height:100vh;-webkit-font-smoothing:antialiased;}
.inner{max-width:1080px;margin:0 auto;}
.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;font-weight:600;
  color:var(--accent);margin:0 0 6px;}
h1{font-size:clamp(26px,4vw,38px);line-height:1.12;margin:0 0 8px;font-weight:680;
  letter-spacing:-.01em;text-wrap:balance;}
.lede{color:var(--ink-2);font-size:16px;max-width:65ch;margin:0 0 28px;}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:36px;}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 18px 16px;}
.tile-value{font-size:32px;font-weight:680;letter-spacing:-.02em;line-height:1;}
.tile-label{font-size:13px;color:var(--ink-2);margin-top:8px;}
.tile-sub{font-size:12px;color:var(--muted);margin-top:3px;}
.tile-accent .tile-value{color:var(--accent);}
.tile-attn .tile-value{color:var(--attn);}
.part{margin:40px 0 8px;padding-top:20px;border-top:2px solid var(--border);}
.part-eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;font-weight:700;color:var(--muted);}
.part h2{font-size:23px;margin:4px 0 4px;font-weight:660;letter-spacing:-.01em;}
.part-note{color:var(--ink-2);font-size:14px;margin:0 0 8px;max-width:65ch;}
.grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;margin-top:18px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 20px 22px;}
.card h3{font-size:15px;margin:0 0 2px;font-weight:640;}
.card .sub{font-size:12.5px;color:var(--muted);margin:0 0 16px;}
.bars{display:flex;flex-direction:column;gap:9px;}
.bar-row{display:grid;grid-template-columns:minmax(118px,40%) 1fr;align-items:center;gap:10px;}
.bar-label{font-size:13px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bar-track{position:relative;display:flex;align-items:center;min-height:20px;}
.bar-fill{height:16px;background:var(--accent);border-radius:0 4px 4px 0;min-width:2px;}
.bar-fill.muted{background:var(--muted-fill);}
.bar-val{font-size:12.5px;color:var(--ink-2);margin-left:9px;white-space:nowrap;
  font-variant-numeric:tabular-nums;}
.heat{display:grid;gap:2px;overflow-x:auto;}
.heat-corner{}
.heat-colhead,.heat-rowhead{font-size:11.5px;color:var(--ink-2);padding:4px 6px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.heat-colhead{align-self:end;}
.heat-rowhead{white-space:normal;line-height:1.2;align-self:center;}
.heat-cell{min-height:34px;display:flex;align-items:center;justify-content:center;
  font-size:13px;font-variant-numeric:tabular-nums;border-radius:4px;background:var(--grid);
  color:var(--ink-2);}
.heat-cell.strong{color:#fff;font-weight:600;}
.split{margin-top:4px;}
.split-bar{display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px;}
.split-high{background:var(--attn);}
.split-low{background:var(--muted-fill);}
.split-legend{display:flex;flex-wrap:wrap;gap:18px;margin-top:12px;font-size:13px;color:var(--ink-2);}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px;vertical-align:middle;}
.dot-high{background:var(--attn);} .dot-low{background:var(--muted-fill);}
.flag-table{width:100%;border-collapse:collapse;font-size:13px;}
.flag-table th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);font-weight:600;padding:0 8px 10px;border-bottom:1px solid var(--border);}
.flag-table th.num,.flag-table td.num{text-align:right;font-variant-numeric:tabular-nums;}
.flag-table td{padding:11px 8px;border-bottom:1px solid var(--border);vertical-align:middle;}
.flag-name{color:var(--ink);margin-bottom:6px;}
.mini{height:5px;background:var(--grid);border-radius:3px;overflow:hidden;max-width:260px;}
.mini-fill{height:100%;border-radius:3px;}
.mini-high{background:var(--attn);} .mini-low{background:var(--muted-fill);}
.chip{font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap;}
.chip-high{background:rgba(var(--attn-rgb),.16);color:var(--attn);}
.chip-low{background:var(--grid);color:var(--ink-2);}
.acc-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:14px;}
.acc{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;}
.acc-val{font-size:26px;font-weight:680;color:var(--good);}
.acc-label{font-size:13px;color:var(--ink-2);margin-top:6px;}
.acc-sub{font-size:11.5px;color:var(--muted);margin-top:3px;}
.empty{color:var(--muted);font-size:13px;font-style:italic;}
.pending{background:var(--accent-weak);border:1px dashed rgba(var(--accent-rgb),.5);
  border-radius:12px;padding:16px 18px;font-size:13.5px;color:var(--ink-2);margin-top:18px;}
.pending strong{color:var(--ink);}
.foot{margin-top:44px;padding-top:18px;border-top:1px solid var(--border);
  font-size:12px;color:var(--muted);line-height:1.7;}
.foot b{color:var(--ink-2);font-weight:600;}
"""


def build_html(df, meta):
    total = len(df)
    fstats = flag_stats(df, total)
    acc = accuracy(df)

    # KPI hero row
    axes_present = sum(1 for _, col, _ in EQUITY_AXES
                       if col in df.columns and df[col].map(lambda x: str(x).strip() != "").any())
    kpis = [
        kpi_tile(f"{total:,}", "Funding requests classified"),
        kpi_tile(f"{axes_present}", "Equity axes classified", "ethnic · gender · sexual", "accent"),
        kpi_tile(fmt_pct(fstats["rows_any_pct"]), "Requests with a review flag",
                 f"{fstats['rows_any']:,} of {total:,} records"),
        kpi_tile(f"{fstats['high']:,}", "High-priority review items",
                 f"+ {fstats['low']:,} low-priority notes", "attn"),
    ]

    # Part A — equity distributions
    a_cards = []
    for title, col, _gen in EQUITY_AXES:
        rows = distribution(df, col, total)
        if not rows:
            continue
        max_count = max(c for _, c, _, _ in rows)
        served = sum(c for _, c, _, g in rows if not g)
        sub = f"{served:,} of {total:,} requests name a specific group"
        a_cards.append(
            f'<div class="card"><h3>{esc(title)}</h3><div class="sub">{esc(sub)}</div>'
            f'{bar_list(rows, total, max_count)}</div>'
        )

    rl, cl, mat, mx = crosstab(df, COL["ethnic1"], COL["gender"])
    heat_card = (
        '<div class="card"><h3>Intersection of ethnic origin × gender</h3>'
        '<div class="sub">Requests naming a specific group on both axes '
        '(the intersectional target population)</div>'
        f'{heatmap(rl, cl, mat, mx)}</div>'
    )

    # Sector / focus-area panels: render if present, else a pending note.
    sector_present = COL["sector"] in df.columns and df[COL["sector"]].map(lambda x: str(x).strip() != "").any()
    ah_present = COL["ah"] in df.columns and df[COL["ah"]].map(lambda x: str(x).strip() != "").any()
    ecd_present = COL["ecd"] in df.columns and df[COL["ecd"]].map(lambda x: str(x).strip() != "").any()

    pending_html = ""
    focus_card = ""
    if ah_present or ecd_present:
        focus_card = focus_area_card(df, total)
    if not (sector_present or ah_present or ecd_present):
        pending_html = (
            '<div class="pending"><strong>Pending import.</strong> '
            'Sector classification and the two ECF focus areas — '
            '<strong>Affordable Housing (AH)</strong> and '
            '<strong>Early Childhood Development (ECD)</strong> — were hand-classified '
            'and will appear here as their own distribution + intersection panels once '
            'imported into <em>FR&nbsp;testing.xlsx</em> and the generator is run in '
            '<em>live</em> mode.</div>'
        )

    # Part B — operations
    b_priority = (
        '<div class="card"><h3>Review load by priority</h3>'
        '<div class="sub">Flags are review metadata only — they never change a '
        'classification. Low-priority notes can be batch-skipped.</div>'
        f'{priority_split(fstats)}</div>'
    )
    b_flags = (
        '<div class="card" style="grid-column:1/-1;"><h3>Most common review flags</h3>'
        f'<div class="sub">Top {TOP_FLAGS} of {len(fstats["counter"])} distinct flags · '
        f'{fstats["total_instances"]:,} total flag instances across {total:,} records</div>'
        f'{flag_table(fstats, total)}</div>'
    )

    acc_tiles = []
    for name, n, agree, pct in acc:
        if pct is None:
            acc_tiles.append(
                f'<div class="acc"><div class="acc-val" style="color:var(--muted)">—</div>'
                f'<div class="acc-label">{esc(name)}</div>'
                f'<div class="acc-sub">not audited</div></div>')
        else:
            acc_tiles.append(
                f'<div class="acc"><div class="acc-val">{fmt_pct(pct)}</div>'
                f'<div class="acc-label">{esc(name)} agreement</div>'
                f'<div class="acc-sub">{agree:,}/{n:,} audited rows</div></div>')
    any_audited = any(pct is not None for *_, pct in acc)
    acc_card = (
        '<div class="card" style="grid-column:1/-1;"><h3>Engine vs. human agreement</h3>'
        '<div class="sub">Where a reviewer recorded the correct answer, how often the '
        'engine matched (depth-fair label comparison).</div>'
        f'<div class="acc-row">{"".join(acc_tiles)}</div></div>'
    ) if any_audited else ""

    today = date.today().isoformat()
    foot = (
        f'<div class="foot">'
        f'<b>Data source:</b> {esc(meta["source"])} · <b>N =</b> {total:,} requests · '
        f'<b>Generated:</b> {today}.<br>'
        'Classification axes are independent. “General Population” means no specific '
        'group was named for that axis — it is the expected majority for a general-purpose '
        'community fund, not a gap. Review flags are advisory metadata and never alter a '
        'classification. '
        + ("Accuracy figures cover only the subset of rows a human has audited so far."
           if any_audited else "")
        + '</div>'
    )

    body = f"""
<div class="wrap"><div class="inner">
  <p class="eyebrow">Edmonton Community Foundation · Discretionary funding</p>
  <h1>Who discretionary funding serves — and the review load behind it</h1>
  <p class="lede">An automated read of {total:,} discretionary funding requests across three
  equity axes — ethnic &amp; cultural origin, gender identity, and sexual identity — with the
  human-review burden the classification raises.</p>

  <div class="kpi-row">{''.join(kpis)}</div>

  <div class="part">
    <div class="part-eyebrow">Part A — Equity lens</div>
    <h2>Who is served</h2>
    <p class="part-note">The share of requests that name a specific served population on each
    axis. Muted bars are “General Population” (no specific group named); coloured bars are
    the equity-relevant groups.</p>
  </div>
  <div class="grid-2">{''.join(a_cards)}{heat_card}</div>
  {focus_card}
  {pending_html}

  <div class="part">
    <div class="part-eyebrow">Part B — Operations lens</div>
    <h2>Engine QA &amp; review burden</h2>
    <p class="part-note">How much human review the classification asks for, which ambiguities
    drive it, and how well the engine agrees with human reviewers.</p>
  </div>
  <div class="grid-2">{b_priority}{acc_card}{b_flags}</div>

  {foot}
</div></div>
"""
    title = "ECF Discretionary Funding — Classification Overview"
    return f"<title>{title}</title>\n<style>{CSS}</style>\n{body}"


# ---------------------------------------------------------------------------
def main():
    ds = bootstrap.dataset()
    print(f"[dataset] active: {ds.name}  ->  reads {ds.raw_file.name}, writes {ds.output_file.name}")

    report_name = ("stakeholder_dashboard.html" if ds.name == "2025"
                    else f"stakeholder_dashboard_{ds.name}.html")
    # Write into the ACTIVE workspace's Data Sheets folder, not the repo's --
    # they differ whenever ECF_WORKSPACE points at a Desktop folder or a
    # Docker bind mount.
    output_file = paths.DATA_DIR / report_name

    df, meta = load_records(ds)
    total = len(df)
    print(f"Mode: {meta['mode']}  ·  Source: {meta['source']}")
    print(f"Records: {total}")

    # Console sanity summary (matches the plan's verification numbers).
    fstats = flag_stats(df, total)
    print(f"Rows with any flag: {fstats['rows_any']} ({fstats['rows_any_pct']:.1f}%)")
    print(f"Flag instances: {fstats['total_instances']}  "
          f"(high {fstats['high']} / low {fstats['low']})")
    for title, col, _ in EQUITY_AXES:
        rows = distribution(df, col, total)
        if rows:
            top = rows[0]
            print(f"  {title}: {len(rows)} distinct; top = {top[0]} ({top[2]:.1f}%)")

    out_html = build_html(df, meta)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(out_html, encoding="utf-8")
    print(f"\nWritten to: {output_file}")


if __name__ == "__main__":
    main()
