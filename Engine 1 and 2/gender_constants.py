"""
gender_constants.py
-------------------
Gender Identity classifier — all data constants.
No logic. Imported by Gender_SexID.py.
"""

# ---------------------------------------------------------------------------
# Output category labels (verbatim — match taxonomy sheet)
# ---------------------------------------------------------------------------
GENDER_WOMEN_GIRLS = "Women and/or girls"
GENDER_MEN_BOYS    = "Men and/or boys"
GENDER_TWO_SPIRIT  = "Two-Spirit"
GENDER_OTHER       = "Other (Agender, Gender fluid, Gender neutral, Genderqueer, Non-binary, Transgender)"
GENDER_MULTIPLE    = "Multiple gender identities"
GENDER_GENERAL_POP = "General Population (No specific gender served)"

# ---------------------------------------------------------------------------
# Output column names
# ---------------------------------------------------------------------------
OUTPUT_GENDER      = "Gender Id - FR9"
OUTPUT_GENDER_FLAG = "Gender Classification Flag"

# ---------------------------------------------------------------------------
# Identity key → output label
# Each "Other (…)" identity key maps to the same label (the six subtypes are
# individually distinct for the Multiple rule, but collapse to one label when
# only one is detected).
# ---------------------------------------------------------------------------
IDENTITY_KEY_TO_LABEL = {
    "women_girls":    GENDER_WOMEN_GIRLS,
    "men_boys":       GENDER_MEN_BOYS,
    "two_spirit":     GENDER_TWO_SPIRIT,
    "agender":        GENDER_OTHER,
    "gender_fluid":   GENDER_OTHER,
    "gender_neutral": GENDER_OTHER,
    "genderqueer":    GENDER_OTHER,
    "non_binary":     GENDER_OTHER,
    "transgender":    GENDER_OTHER,
}

# Short name used inside "Multiple: …" flag text
IDENTITY_KEY_SHORT_LABEL = {
    "women_girls":    "women/girls",
    "men_boys":       "men/boys",
    "two_spirit":     "Two-Spirit",
    "agender":        "agender",
    "gender_fluid":   "gender fluid",
    "gender_neutral": "gender neutral",
    "genderqueer":    "genderqueer",
    "non_binary":     "non-binary",
    "transgender":    "transgender",
}

# ---------------------------------------------------------------------------
# Term patterns
# Format: (regex, identity_key, extra_flag_key | None)
# extra_flag_key: "sex_term" when match comes from female/male (biological-sex term)
#
# Ordering note — female BEFORE male:
#   Word-boundary anchors (\b) already prevent \bmale\b from matching inside
#   "female" (the 'f' and 'e' in "fe" are word-chars, so no \b before the 'm').
#   The list ordering is belt-and-suspenders for readability and resilience.
#
# bare "queer" and bare "trans" are NOT listed here — they are handled
# separately in Gender_SexID.extract_gender_candidates() because each needs
# a context check to decide whether to attach an ambiguity flag.
# ---------------------------------------------------------------------------
GENDER_TERM_PATTERNS = [
    # women_girls — female first
    (r"\bfemales?\b", "women_girls", "sex_term"),
    (r"\bwomen\b", "women_girls", None),
    (r"\bwoman\b", "women_girls", None),
    (r"\bgirls?\b", "women_girls", None),
    # men_boys
    (r"\bmales?\b", "men_boys", "sex_term"),
    (r"\bmen\b", "men_boys", None),
    (r"\bman\b", "men_boys", None),
    (r"\bboys?\b", "men_boys", None),
    # two_spirit
    (r"\btwo[\-\s]spirited?\b", "two_spirit", None),
    (r"\b2[\-\s]spirited?\b", "two_spirit", None),
    (r"\btwospirit\b", "two_spirit", None),
    # other — each is a distinct identity (drives Multiple if 2+ present)
    (r"\bagender\b", "agender", None),
    (r"\bgender[\-\s]?fluid\b", "gender_fluid", None),
    (r"\bgenderfluid\b", "gender_fluid", None),
    (r"\bgender[\-\s]?neutral\b", "gender_neutral", None),
    (r"\bgenderqueer\b", "genderqueer", None),
    (r"\bgender[\-\s]queer\b", "genderqueer", None),
    # non_binary
    (r"\bnon[\-\s]?binary\b", "non_binary", None),
    (r"\benby\b", "non_binary", None),
    # transgender (full word — bare "trans" handled separately)
    (r"\btransgender\b", "transgender", None),
]

# Special-case patterns whose flag depends on context — handled inline in extractor
BARE_QUEER_PATTERN = r"\bqueer\b"
BARE_TRANS_PATTERN = r"\btrans\b"
# Used to detect "gender queer" / "genderqueer" context so bare-queer flag is suppressed
GENDER_QUEER_CONTEXT = r"\bgender[\-\s]?queer\b|\bgenderqueer\b"

# ---------------------------------------------------------------------------
# Flag strings (all live here so a reviewer can grep one file)
# ---------------------------------------------------------------------------
FLAG_SEX_TERM = "Sex term (female/male) used - verify gender-identity vs. biological-sex intent"
FLAG_QUEER_AMBIGUOUS = "Ambiguous 'queer' - may mean genderqueer (gender) or a sexual-identity term - verify"
FLAG_BARE_TRANS = "Possible false 'trans' token - verify transgender vs. trans- prefix word"
FLAG_ASPIRATIONAL = "Aspirational/future language - group may not be current served population"
FLAG_TWO_SPIRIT_INDIG = "Two-Spirit present - also an Indigenous signal - cross-check ethnic classification"
FLAG_NEGATION = "Negation detected - verify exclusion vs inclusion intent"

# ---------------------------------------------------------------------------
# Sexual Identity — output labels, columns, signals, flags
# ---------------------------------------------------------------------------
SEXUAL_2SLGBTQIA   = "2SLGBTQIA+"
SEXUAL_GENERAL_POP = "General Population (No specific sexual identity served)"

OUTPUT_SEXUAL      = "Sexual Id - FR10"
OUTPUT_SEXUAL_FLAG = "Sexual Classification Flag"

# Gender-diverse identity keys that imply 2SLGBTQIA+ (all gender keys except women/men)
_SEXUAL_GENDER_DIVERSE_KEYS = {
    "two_spirit", "agender", "gender_fluid", "gender_neutral",
    "genderqueer", "non_binary", "transgender",
}

# Single source of truth — reuse GENDER_TERM_PATTERNS; no re-listing of trans/non-binary/etc.
# BARE_TRANS_PATTERN appended because bare "trans" also signals 2SLGBTQIA+.
SEXUAL_GENDER_DIVERSE_PATTERNS = (
    [pat for pat, key, _ in GENDER_TERM_PATTERNS if key in _SEXUAL_GENDER_DIVERSE_KEYS]
    + [BARE_TRANS_PATTERN]
)

# Explicit orientation terms + acronym family.
# "queer" is treated as an orientation term here — presence alone → 2SLGBTQIA+,
# no prefix-context check needed (that check only matters for gender classification).
SEXUAL_ORIENTATION_PATTERNS = [
    r"\blesbians?\b",
    r"\bgay\b",
    r"\bbisexual\b",
    r"\bqueer\b",
    r"\bintersex\b",
    r"\basexual\b",
    r"\bpansexual\b",
    # Acronym family: optional 2s prefix, optional q/ia/2s suffix, optional +
    # normalize_text() replaces literal + with space, so \+? matches gracefully without it.
    r"\b(2s)?lgbt(?:q(?:ia?|2s)?)?\+?(?!\w)",
]

# Sexual identity flag strings
SFLAG_NEGATION     = "Negation detected - verify exclusion vs inclusion intent"
SFLAG_GENDER_TERM  = "Signal is a gender-identity term (trans/two-spirit/non-binary/…) - 2SLGBTQIA+ via umbrella, verify sexual-orientation intent"
SFLAG_ASPIRATIONAL = "Aspirational/future language - group may not be current served population"
