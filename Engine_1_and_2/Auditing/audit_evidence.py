"""
audit_evidence.py
-----------------
Read-only audit explainer. Re-scans a row against the same term sets used
by the engine and surfaces which terms matched, in which column, and whether
negation or example-mention guards suppressed them.

Public functions:
    ethnic_evidence(row, taxonomy_entries) -> str
    gender_evidence(row) -> str
    sexual_evidence(row) -> str

Never classifies. Never modifies engine output. Uses the engine's own
constants as the single source of truth so evidence stays in sync.
"""

import re
import pandas as pd

from ethnic_taggerv3 import (
    INPUT_COLS_PRIORITY,
    normalize_text,
    apply_identity_phrase_rewrites,
    is_negated,
    is_example_mention,
)
from constants import (
    PATTERN_RULES, COUNTRY_REGION_MAP, ALWAYS_MULTIPLE_COMPOUNDS,
    BROAD_IDENTITY_KEYWORDS, ORG_NAME_ETHNICITY_MAP, BIPOC_KEYWORDS,
)
from gender_constants import (
    GENDER_TERM_PATTERNS,
    BARE_QUEER_PATTERN, BARE_TRANS_PATTERN, UMBRELLA_ACRONYM_PATTERN,
    SEXUAL_GENDER_DIVERSE_PATTERNS, SEXUAL_ORIENTATION_PATTERNS,
    ORG_NAME_CONTEXT_PATTERNS, AMBIGUOUS_CODED_TERMS,
)

snippet_WINDOW = 60

def normed(row, col):
    val = row.get(col, "")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if not isinstance(val, str):
        return ""
    return apply_identity_phrase_rewrites(normalize_text(val))

def raw(row, col):
    val = row.get(col, "")
    if val is None or not isinstance(val, str):
        return ""
    return val

def snippet(text, m_start, m_end):
    start = max(0, m_start - snippet_WINDOW)
    end   = min(len(text), m_end + snippet_WINDOW)
    fragment = text[start:end].replace("\n", " ").strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f'"{prefix}{fragment}{suffix}"'

def best_snippet(matched_term, normed_text, normed_start, normed_end, raw_text):
    """Use raw text for the snippet where possible; fall back to normed for
    rewritten tokens (e.g. 'africancanadian') that don't exist in the raw string."""
    if raw_text:
        m = re.search(r'\b' + re.escape(matched_term) + r'\b', raw_text, re.IGNORECASE)
        if m:
            return snippet(raw_text, m.start(), m.end())
    return snippet(normed_text, normed_start, normed_end)

def fmt(matched_term, source, col, negated, example, normed_text, n_start, n_end, raw_text):
    qualifier = "{NEGATED}" if negated else ("{EXAMPLE}" if example else "")
    snip = best_snippet(matched_term, normed_text, n_start, n_end, raw_text)
    return f"{matched_term} [{source}, {col}]{qualifier}: {snip}"

def org_ambiguous_evidence(row):
    """
    Scan each input column for org-name context and ambiguous coded terms.
    Uses norm_text (not normed) as the local variable name to avoid the
    outer normed() function being shadowed.
    Returns a list of evidence strings ready to extend into a parts list.
    """
    parts = []
    seen = set()
    for col in INPUT_COLS_PRIORITY:
        val = row.get(col, "")
        if not val or not isinstance(val, str):
            continue
        norm_text = apply_identity_phrase_rewrites(normalize_text(val))
        if not norm_text:
            continue
        for pat in ORG_NAME_CONTEXT_PATTERNS:
            m = re.search(pat, norm_text, re.IGNORECASE)
            if m:
                key = ("org_context", col)
                if key not in seen:
                    seen.add(key)
                    snip = snippet(norm_text, m.start(), m.end())
                    parts.append(f"org_context [{col}]: {snip}")
                break
        for pat in AMBIGUOUS_CODED_TERMS:
            m = re.search(pat, norm_text, re.IGNORECASE)
            if m:
                term = m.group(0)
                key = (term.lower(), col)
                if key not in seen:
                    seen.add(key)
                    snip = snippet(norm_text, m.start(), m.end())
                    parts.append(f"ambiguous_coded({term}) [{col}]: {snip}")
    return parts

def ethnic_evidence(row, taxonomy_entries):
    """
    Re-scan each input column for ethnic signals. Returns a pipe-separated
    evidence string: one entry per distinct (term, column) pair found.
    Matches use the engine's own patterns so evidence stays in sync.
    """
    parts = []
    seen = set()   # (matched_term.lower(), col) — dedupe within column

    for col in INPUT_COLS_PRIORITY:
        norm_text = normed(row, col)
        raw_text  = raw(row, col)
        if not norm_text:
            continue

        # Cases 1-3: taxonomy keywords
        for entry in taxonomy_entries:
            kw = entry["keyword"]
            if not kw:
                continue
            pat = re.compile(r'\b' + re.escape(kw) + r's?\b', re.IGNORECASE)
            for m in pat.finditer(norm_text):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                label   = entry.get("level3") or entry.get("level2") or entry.get("level1") or kw
                negated = is_negated(kw, norm_text)
                example = is_example_mention(kw, norm_text)
                parts.append(fmt(term, f"taxonomy({label})", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

        # Case 9: BIPOC keywords
        for kw_pat in BIPOC_KEYWORDS:
            for m in re.finditer(kw_pat, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                negated = is_negated(term, norm_text)
                example = is_example_mention(term, norm_text)
                parts.append(fmt(term, "bipoc", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

        # Compound identity phrases (ALWAYS_MULTIPLE → always Multi)
        for compound_pat in ALWAYS_MULTIPLE_COMPOUNDS:
            for m in re.finditer(compound_pat, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                parts.append(fmt(term, "compound", col, False, False,
                                  norm_text, m.start(), m.end(), raw_text))

        # Case 4: directional / structural pattern rules
        for pat_str, l1, l2, l3 in PATTERN_RULES:
            for m in re.finditer(pat_str, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                label = l3 or l2 or l1
                parts.append(fmt(term, f"pattern({label})", col, False, False,
                                  norm_text, m.start(), m.end(), raw_text))

        # Cases 6-7: country / nationality map
        for country, (l1, l2, l3) in COUNTRY_REGION_MAP.items():
            direct  = re.search(r'\b' + re.escape(country) + r's?\b', norm_text, re.IGNORECASE)
            from_ph = re.search(r'\bfrom\s+' + re.escape(country) + r's?\b', norm_text, re.IGNORECASE)
            m = direct or from_ph
            if not m:
                continue
            term = m.group(0)
            key  = (country.lower(), col)
            if key in seen:
                continue
            seen.add(key)
            label   = l3 or l2 or l1
            negated = is_negated(term, norm_text)
            parts.append(fmt(term, f"country({label})", col, negated, False,
                               norm_text, m.start(), m.end(), raw_text))

        # Case 9b: broad identity labels
        for kw_pat in BROAD_IDENTITY_KEYWORDS:
            for m in re.finditer(kw_pat, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                negated = is_negated(term, norm_text)
                example = is_example_mention(term, norm_text)
                parts.append(fmt(term, "broad_identity", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

        # Case 10: org-name lookup
        for org_name, (l1, l2, l3) in ORG_NAME_ETHNICITY_MAP.items():
            m = re.search(r'\b' + re.escape(org_name) + r'\b', norm_text, re.IGNORECASE)
            if not m:
                continue
            term = m.group(0)
            key  = (term.lower(), col)
            if key in seen:
                continue
            seen.add(key)
            label = l3 or l2 or l1
            parts.append(fmt(term, f"org_lookup({label})", col, False, False,
                               norm_text, m.start(), m.end(), raw_text))

    return " | ".join(parts)

def gender_evidence(row):
    """
    Re-scan each input column for gender-identity signals.
    Returns a pipe-separated evidence string.
    """
    parts = []
    seen  = set()

    for col in INPUT_COLS_PRIORITY:
        norm_text = normed(row, col)
        raw_text  = raw(row, col)
        if not norm_text:
            continue

        # Standard GENDER_TERM_PATTERNS
        for pat_str, identity_key, _ in GENDER_TERM_PATTERNS:
            for m in re.finditer(pat_str, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                negated = is_negated(term, norm_text)
                example = is_example_mention(term, norm_text)
                parts.append(fmt(term, f"gender({identity_key})", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

        # Bare "queer" (context-sensitive in gender classifier)
        for m in re.finditer(BARE_QUEER_PATTERN, norm_text, re.IGNORECASE):
            term = m.group(0)
            key  = (term.lower(), col)
            if key in seen:
                continue
            seen.add(key)
            negated = is_negated(term, norm_text)
            example = is_example_mention(term, norm_text)
            parts.append(fmt(term, "gender(genderqueer/bare)", col, negated, example,
                               norm_text, m.start(), m.end(), raw_text))

        # Bare "trans" (context-sensitive in gender classifier)
        for m in re.finditer(BARE_TRANS_PATTERN, norm_text, re.IGNORECASE):
            term = m.group(0)
            key  = (term.lower(), col)
            if key in seen:
                continue
            seen.add(key)
            negated = is_negated(term, norm_text)
            example = is_example_mention(term, norm_text)
            parts.append(fmt(term, "gender(transgender/bare)", col, negated, example,
                               norm_text, m.start(), m.end(), raw_text))

        # 2SLGBTQIA+ umbrella acronym
        for m in re.finditer(UMBRELLA_ACRONYM_PATTERN, norm_text, re.IGNORECASE):
            term = m.group(0)
            key  = (term.lower(), col)
            if key in seen:
                continue
            seen.add(key)
            negated = is_negated(term, norm_text)
            example = is_example_mention(term, norm_text)
            parts.append(fmt(term, "gender(lgbtq_umbrella)", col, negated, example,
                               norm_text, m.start(), m.end(), raw_text))

    parts.extend(org_ambiguous_evidence(row))
    return " | ".join(parts)

def sexual_evidence(row):
    """
    Re-scan each input column for sexual-orientation signals.
    Returns a pipe-separated evidence string.
    """
    parts = []
    seen  = set()

    for col in INPUT_COLS_PRIORITY:
        norm_text = normed(row, col)
        raw_text  = raw(row, col)
        if not norm_text:
            continue

        # Gender-diverse identity terms that imply 2SLGBTQIA+
        for pat_str in SEXUAL_GENDER_DIVERSE_PATTERNS:
            for m in re.finditer(pat_str, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                negated = is_negated(term, norm_text)
                example = is_example_mention(term, norm_text)
                parts.append(fmt(term, "sexual(gender_diverse)", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

        # Explicit orientation terms and acronyms
        for pat_str in SEXUAL_ORIENTATION_PATTERNS:
            for m in re.finditer(pat_str, norm_text, re.IGNORECASE):
                term = m.group(0)
                key  = (term.lower(), col)
                if key in seen:
                    continue
                seen.add(key)
                negated = is_negated(term, norm_text)
                example = is_example_mention(term, norm_text)
                parts.append(fmt(term, "sexual(orientation)", col, negated, example,
                                  norm_text, m.start(), m.end(), raw_text))

    return " | ".join(parts)
