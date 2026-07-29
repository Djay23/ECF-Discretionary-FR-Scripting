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
# lgbtq_umbrella short-circuits to GENDER_MULTIPLE in resolve_gender() before
# IDENTITY_KEY_TO_LABEL is consulted; GENDER_OTHER here is a safe fallback only.
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
    "lgbtq_umbrella": GENDER_OTHER,
    # gender_diverse short-circuits to GENDER_MULTIPLE in resolve_gender()
    # (same shape as lgbtq_umbrella) before this table is consulted.
    "gender_diverse": GENDER_OTHER,
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
    "lgbtq_umbrella": "2SLGBTQIA+ umbrella",
    "gender_diverse": "gender-diverse",
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
    (r"\bfemales?\b", "women_girls", None),
    # \bwomens?\b (not \bwomen\b) so the normalized form of "Womens'" (trailing
    # apostrophe stripped to nothing by normalize_text, leaving "womens" as one
    # token with no word boundary after "women") is still detected.
    (r"\bwomens?\b", "women_girls", None),
    (r"\bwoman\b", "women_girls", None),
    (r"\bgirls?\b", "women_girls", None),
    # women_girls — familial / relational (unambiguous gendered terms)
    # normalize_text strips apostrophes/punctuation, so "mothers'" and "mothers" both → \bmothers\b
    (r"\bmothers?\b", "women_girls", None),
    (r"\bmoms?\b", "women_girls", None),
    (r"\bmaternal\b", "women_girls", None),
    (r"\bmatriarchs?\b", "women_girls", None),
    (r"\bmatriarchal\b", "women_girls", None),
    (r"\bsisters?\b", "women_girls", None),
    (r"\bdaughters?\b", "women_girls", None),
    (r"\bgrandmothers?\b", "women_girls", None),
    (r"\baunts?\b", "women_girls", None),
    (r"\bwidows?\b", "women_girls", None),
    (r"\bladies\b", "women_girls", None),
    (r"\blady\b", "women_girls", None),
    # French: "femme(s)" = French for woman/women. Ambiguous with the
    # English coded-slang sense (see AMBIGUOUS_CODED_TERMS below) — both
    # mechanisms fire together: this classifies, FLAG_AMBIGUOUS_TERM still
    # flags it so a reviewer double-checks which sense applies.
    (r"\bfemmes?\b", "women_girls", None),
    # men_boys
    (r"\bmales?\b", "men_boys", None),
    # \bmens?\b (not \bmen\b) — same normalized-possessive-plural reasoning as women.
    (r"\bmens?\b", "men_boys", None),
    (r"\bman\b", "men_boys", None),
    (r"\bboys?\b", "men_boys", None),
    # men_boys — familial / relational
    (r"\bfathers?\b", "men_boys", None),
    (r"\bdads?\b", "men_boys", None),
    (r"\bpaternal\b", "men_boys", None),
    (r"\bpatriarchs?\b", "men_boys", None),
    (r"\bpatriarchal\b", "men_boys", None),
    (r"\bbrothers?\b", "men_boys", None),
    (r"\bsons?\b", "men_boys", None),
    (r"\bgrandfathers?\b", "men_boys", None),
    (r"\buncles?\b", "men_boys", None),
    (r"\bwidowers?\b", "men_boys", None),
    (r"\bgentlem[ae]n\b", "men_boys", None),
    # French: "homme(s)" = French for man/men.
    (r"\bhommes?\b", "men_boys", None),
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
    # gender-diverse — a distinct umbrella concept: always
    # routes to Multiple gender identities (see resolve_gender) and, via
    # SEXUAL_GENDER_DIVERSE_KEYS below, to 2SLGBTQIA+ on the sexual axis.
    (r"\bgender[\-\s]?diverse\b", "gender_diverse", None),
]

# Special-case patterns whose flag depends on context — handled inline in extractor
BARE_QUEER_PATTERN = r"\bqueer\b"
BARE_TRANS_PATTERN = r"\btrans\b"
# Used to detect "gender queer" / "genderqueer" context so bare-queer flag is suppressed
GENDER_QUEER_CONTEXT = r"\bgender[\-\s]?queer\b|\bgenderqueer\b"

# Shared acronym pattern — referenced by SEXUAL_ORIENTATION_PATTERNS and the gender
# umbrella scan so the regex lives in exactly one place.
# normalize_text() replaces literal + with space, so \+? matches gracefully without it.
UMBRELLA_ACRONYM_PATTERN = r"\b(2s)?lgbt(?:q(?:ia?|2s)?)?\+?(?!\w)"

# ---------------------------------------------------------------------------
# Flag strings (all live here so a reviewer can grep one file)
# ---------------------------------------------------------------------------
FLAG_ASPIRATIONAL     = "Aspirational/future language - group may not be current served population"
FLAG_TWO_SPIRIT_INDIG = "Two-Spirit present - also an Indigenous signal - cross-check ethnic classification"
FLAG_NEGATION         = ("Matched term appears near a negation word (e.g. \"not\", \"excluding\") "
                          "- confirm the population is served, not excluded")
FLAG_UMBRELLA_ACRONYM = "Gender identity inferred from 2SLGBTQIA+ umbrella acronym - umbrella also spans cisgender orientations; verify served population"
FLAG_ORG_NAME         = "Gender/sexual term appears inside an organization or proper name - verify served population vs organization name"
FLAG_AMBIGUOUS_TERM   = "Ambiguous coded gender/orientation term (femme/masc/butch/...) - verify served population on both gender and sexual-identity axes"

# ---------------------------------------------------------------------------
#
# Bare relational-male nouns (fathers/brothers/sons/dads) are ambiguous:
# they can name the actual served population ("a fathers group for new
# parents" -> Men and/or boys) OR merely mention an absent/left-behind
# family member while the real served population is someone else (e.g.
# "...their fathers... remain in Ukraine" -- the served population is
# Ukrainian youth, not fathers). Mirrors the served-vs-mentioned weak-role
# pattern already used in ethnic_taggerv3.infer_role (org_name/provider/
# example/aspirational) and in extract_gender_candidates' existing
# org-echo rescue: a match sitting in one of these LEFT-BEHIND frames is a
# weak "family_context" occurrence, not a served-population claim, unless
# a later occurrence of the same term IS in a served frame.
# ---------------------------------------------------------------------------
RELATIONAL_MALE_GUARD_PATTERNS = [
    r"\bfathers?\b",
    r"\bdads?\b",
    r"\bbrothers?\b",
    r"\bsons?\b",
]

# A relational-male noun is the SERVED population (not an incidental family
# mention) when it sits in an explicit served frame -- immediately followed by
# a service noun ("a fathers GROUP", "dads PROGRAM") or preceded by a serve
# verb ("FOR fathers", "SUPPORTING dads"). Without such a frame (e.g. "their
# fathers were not allowed to leave", "dad time", "her little brother kenny")
# the mention is weak/incidental. Checked per-occurrence in
# extract_gender_candidates.
RELATIONAL_MALE_SERVED_AFTER_PATTERNS = [
    r"^\s*(?:group|groups|program|programme|club|circle|mentorship|network|drop[\s-]*in)\b",
]
RELATIONAL_MALE_SERVED_BEFORE_PATTERNS = [
    r"\b(?:for|serving|serves?|support|supports?|supporting|empowers?|empowering|"
    r"mentor(?:s|ing)?|helps?|helping)\s+(?:the\s+|new\s+|young\s+|our\s+)?$",
]

FAMILY_LEFT_BEHIND_BEFORE_PATTERNS = [
    r"\bseparated\s+from\s*(?:their|his|her)?\s*$",
    r"\bwithout\s+(?:their|his|her)\s*$",
]

FAMILY_LEFT_BEHIND_AFTER_PATTERNS = [
    # Filler-word allowance (other family nouns: "friends", "extended
    # family", commas) between the relational term and the verb phrase
    # that places it elsewhere/absent -- same bleed-prevention shape as
    # ROLE_ORG_NAME_AFTER_PATTERNS (anchored, bounded filler).
    r"^\s*(?:\w+\s+){0,6}remain(?:s|ed|ing)?\s+(?:in|behind)\b",
    r"^\s*(?:\w+\s+){0,6}(?:stay(?:ed|ing)?|left)\s+behind\b",
    r"^\s*(?:\w+\s+){0,6}back\s+(?:home|in\b)",
    r"^\s*(?:\w+\s+){0,6}still\s+(?:in|living|residing)\b",
    r"^\s*(?:\w+\s+){0,6}unable\s+to\s+(?:join|leave|come)\b",
]

# ---------------------------------------------------------------------------
# Gender-neutral organization names.
# A handful of well-known org names contain gender words but serve the
# GENERAL population: "Boys & Girls Club" (youth), "Big Brothers Big Sisters"
# (mentorship). A gender term (boys/girls/brothers/sisters) matched INSIDE
# one of these name spans is part of the organization's name, not a
# served-population signal, so extract_gender_candidates skips that exact
# occurrence. (normalize_text strips '&' to a space: "Boys & Girls" ->
# "boys girls"; the explicit "and" is optional in the patterns.)
# ---------------------------------------------------------------------------
GENDER_NEUTRAL_ORG_PATTERNS = [
    r"\bbig\s+brothers?\s+big\s+sisters?\b",
    r"\bbig\s+brothers?\b",
    r"\bbig\s+sisters?\b",
    r"\bboys?\s+(?:and\s+)?girls?\s+clubs?\b",
    r"\bgirls?\s+(?:and\s+)?boys?\s+clubs?\b",
]

# Curated known gender-serving org names -- consulted as a LAST RESORT (only
# when the body carries no served gender signal), mirroring the ethnic
# ORG_NAME_ETHNICITY_MAP. These are specific orgs whose served gender is known
# from outside the FR text: e.g. "E Town Brothers Basketball" runs young-men's
# and Men's competitive leagues, so a row that only names it as a partner would
# otherwise miss (its "brothers" is a partner org name, not a served signal).
# Keyed on a distinctive span of the org name.
GENDER_ORG_NAME_MAP = {
    "e town brothers basketball": GENDER_MEN_BOYS,
}

# ---------------------------------------------------------------------------
# Generalizable silent-body name rule — when the
# body carries NO gender/sexual-identity signal at all (not even a weak
# org-name-echo mention), classify from women/men/2SLGBTQIA+ terms found in
# the RAW funding-request account name instead of defaulting flat to
# General. See Gender_SexID.classify_gender_from_raw_name /
# classify_sexual_from_raw_name.
# ---------------------------------------------------------------------------
GENDER_SILENT_NAME_WOMEN_PATTERN = r"\b(women|woman|girls?|mothers?|sisters?|femmes?)\b"
GENDER_SILENT_NAME_MEN_PATTERN   = r"\b(men|man|boys?|fathers?|brothers?|hommes?)\b"
SEXUAL_SILENT_NAME_PATTERN       = r"\b(pride|queer|trans\w*|2slgbtq\w*|lgbt\w*)\b"

# ---------------------------------------------------------------------------
# Ambiguous coded terms — flag without classifying (femme/masc/butch are
# gender-coded AND lesbian-orientation-adjacent; reviewer checks both axes).
# ---------------------------------------------------------------------------
AMBIGUOUS_CODED_TERMS = [
    r"\bfemme\b",
]

# ---------------------------------------------------------------------------
# Org / proper-name context patterns.
# Run on normalized text (normalize_text lowercases + replaces all
# non-word/non-space chars with space, so apostrophes become spaces:
#   "Women's" → "women s",  "Boys & Girls" → "boys  girls" → "boys girls").
# When any pattern fires alongside a classification, FLAG_ORG_NAME is appended.
# ---------------------------------------------------------------------------
ORG_NAME_CONTEXT_PATTERNS = [
    # "Boys (and) Girls Club" — & normalized to space; explicit "and" optional
    r"\bboys?\s+(?:and\s+)?girls?\s+club\b",
    r"\bgirls?\s+(?:and\s+)?boys?\s+club\b",
    # "[gender word][s] [org noun]" — "womens association", "ladies institute"
    # "women s" (from "Women's") is also matched since 's' token can follow
    r"\b(?:womens?|women\s+s|girls?|mens?|boys?|females?|males?|mothers?|fathers?|ladies|lady)\s+"
    r"(?:club|society|association|institute|foundation|centre|center|council|league|academy|guild|chapter|network|organization)\b",
    # "[org noun] for/of [gender word]" — "institute for women", "foundation for girls"
    r"\b(?:club|society|association|institute|foundation|centre|center|council|league|academy|guild|chapter|network|organization)\s+"
    r"(?:for|of)\s+(?:women|woman|girls?|men|man|boys?|females?|males?|mothers?|fathers?|ladies|lady)\b",
]

# ---------------------------------------------------------------------------
# Sexual Identity — output labels, columns, signals, flags
# ---------------------------------------------------------------------------
SEXUAL_2SLGBTQIA   = "2SLGBTQIA+"
SEXUAL_GENERAL_POP = "General Population (No specific sexual identity served)"

OUTPUT_SEXUAL = "Sexual Id - FR10"
OUTPUT_SEXUAL_FLAG = "Sexual Classification Flag"

# Gender-diverse identity keys that imply 2SLGBTQIA+ (all gender keys except women/men)
SEXUAL_GENDER_DIVERSE_KEYS = {
    "two_spirit", "agender", "gender_fluid", "gender_neutral",
    "genderqueer", "non_binary", "transgender", "gender_diverse",
}

# Single source of truth — reuse GENDER_TERM_PATTERNS; no re-listing of trans/non-binary/etc.
# BARE_TRANS_PATTERN appended because bare "trans" also signals 2SLGBTQIA+.
SEXUAL_GENDER_DIVERSE_PATTERNS = (
    [pat for pat, key, _ in GENDER_TERM_PATTERNS if key in SEXUAL_GENDER_DIVERSE_KEYS]
    + [BARE_TRANS_PATTERN]
)

# Of the SEXUAL_GENDER_DIVERSE_KEYS umbrella, only
# the "gender_diverse" key itself (bare "gender-diverse") is ambiguous enough
# to warrant SFLAG_GENDER_TERM. The other keys (trans/non-binary/two-spirit/
# agender/gender-fluid/gender-neutral/genderqueer) unambiguously belong under
# the 2SLGBTQIA+ umbrella, so flagging every occurrence of those was noise —
# a 2SLGBTQIA+ result from one of them already speaks for itself.
SEXUAL_GENDER_DIVERSE_KEY_ONLY_PATTERNS = [
    pat for pat, key, _ in GENDER_TERM_PATTERNS if key == "gender_diverse"
]

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
    UMBRELLA_ACRONYM_PATTERN,   # single source of truth — defined above
]

# Sexual identity flag strings
SFLAG_NEGATION = ("Matched term appears near a negation word (e.g. \"not\", \"excluding\") "
                   "- confirm the population is served, not excluded")
SFLAG_GENDER_TERM = "2SLGBTQIA+ inferred from a gender-identity term (trans/non-binary/two-spirit/...) not an explicit orientation - verify sexual-identity intent"
SFLAG_ASPIRATIONAL = "Aspirational/future language - group may not be current served population"
