"""
This is a helper file to hold constants used for different cases. This file is accessed by extractors.py
and doesn't write any outputs. Its purpose is to hold constants that are used in multiple places in the code, so that they can be easily updated
in one place if needed.
"""

# ---------------------------------------------------------------------------
# Classification outcome strings (canonical — imported by extractors, resolver)
# ---------------------------------------------------------------------------
MULTIPLE_ETHNIC = "Multiple Ethnic and Cultural Origins"
OTHER_ETHNIC    = "Other Ethnic and Cultural Origins"
GENERAL_POP     = "General Population (No specific ethnic and cultural origin group served)"

# North American Indigenous umbrella-widening rule 
INDIGENOUS_L1 = "North American Indigenous Origins"
INDIGENOUS_UMBRELLA_FLAG = (
    "Review: Indigenous umbrella term co-occurs with specific sub-group(s) - "
    "classified at general North American Indigenous level; verify served population"
)

# 
# ONLY evidence for it is a topic/partnership mention (role "topic_keep"),
# not a genuine served-population claim. The classification itself is
# unaffected -- resolver treats "topic_keep" as served for outcome purposes
# -- this flag only tells a reviewer to double check.
FLAG_INDIGENOUS_TOPIC_VERIFY = (
    "Note (low priority): Indigenous topic/partnership mention - "
    "not confirmed as served population; verify"
)

# ==================================================
# CASE 4 — Structured / directional phrase patterns
# Applied only if no direct taxonomy match found.
# ==================================================
PATTERN_RULES = [
    (r"\bnorth[\s\-]?african\b", "African Origins", "North African Origins", ""),
    (r"\bsouth[\s\-]?african\b", "African Origins", "Southern and East African Origins", ""),
    (r"\beast[\s\-]?african\b", "African Origins", "Southern and East African Origins", ""),
    (r"\bwest[\s\-]?african\b", "African Origins", "Central and West African Origins", ""),
    (r"\bcentral[\s\-]?african\b", "African Origins", "Central and West African Origins", ""),
    (r"\bsub[\s\-]?saharan\b", "African Origins", "Central and West African Origins", ""),
    (r"\bafrican (descent|heritage|origin|ancestry)\b", "African Origins", "", ""),  # "youth of African descent"
    (r"\bsoutheast[\s\-]?asian\b", "Asian Origins", "East and Southeast Asian Origins", ""),
    (r"\bsouth[\s\-]?asian\b", "Asian Origins", "South Asian Origins", ""),
    (r"\beast[\s\-]?asian\b", "Asian Origins", "East and Southeast Asian Origins", ""),
    (r"\bmiddle[\s\-]?eastern\b", "Asian Origins", "West and Central Asian and Middle Eastern Origins", ""),
    (r"\bfirst nations\b", "North American Indigenous Origins", "", ""),
    (r"\bmetis\b", "North American Indigenous Origins", "Métis", ""),
    (r"\binuit\b", "North American Indigenous Origins", "", ""),
    (r"\baboriginal\b","North American Indigenous Origins", "", ""),
    (r"\bindigenous canadian\b", "North American Indigenous Origins", "", ""),
    (r"\bindigenous\b", "North American Indigenous Origins", "", ""),
    (r"\bindiginous\b", "North American Indigenous Origins", "", ""),
    (r"\bindigenious\b", "North American Indigenous Origins", "", ""),
    (r"\bindingeous\b", "North American Indigenous Origins", "", ""),
    # "Treaty 6" intentionally NOT a pattern rule: "on Treaty 6 territory" is a
    # boilerplate land acknowledgment, not a served-population signal, so it
    # must not classify Indigenous on its own (stakeholder ruling). Treaty-6
    # rows that genuinely serve Indigenous people carry another signal
    # (indigenous/métis/first nations) that classifies them. A "Treaty 6" in
    # the org NAME is still caught by the name-only ORG_NAME_ETHNICITY_MAP entry.
    (r"\bnorthern european\b", "European Origins", "Northern European Origins", ""),
    (r"\bsouthern european\b", "European Origins", "Southern European Origins", ""),
    (r"\beast(ern)? european\b", "European Origins", "Eastern European Origins", ""),
    (r"\bwest(ern)? european\b", "European Origins", "Western European Origins", ""),
    (r"\blatino\b", "Latin, Central, and South American Origins", "", ""),
    (r"\blatina\b", "Latin, Central, and South American Origins", "", ""),
    (r"\blatinx\b", "Latin, Central, and South American Origins", "", ""),
    (r"\bsouth[\s\-]?american\b", "Latin, Central, and South American Origins", "", ""),
    (r"\bcentral[\s\-]?american\b", "Latin, Central, and South American Origins", "", ""),
]

# ============================================================
# Terms that must NEVER be added to COUNTRY_REGION_MAP.
#
# Expanding the map to ~200 nationalities looks obviously correct and is not:
# measured over all 448 rows it produced 0 fixes and 4 regressions. Two distinct
# failure modes, both observed in the real corpus:
#
#   1. HOMOGRAPHS — the word is ordinary English far more often than a
#      nationality. "english" appears 19 times, every one of them a LANGUAGE
#      reference ("English as a second language"); adding it flipped four
#      audited-correct rows to European Origins, including a Somali row.
#      "polish" appears once: "final polish for public release".
#
#   2. NATIONALITY-AS-ATTRIBUTE — the word really is the nationality, but it
#      modifies an OBJECT, cuisine, or art form rather than naming a population:
#      "Mongolian yurts" (storage equipment), "pre-hispanic Mexican dance"
#      (an art form). No exclusion list fixes this one -- it is the same
#      served-vs-attribute problem the evidence-role frames exist for -- so it
#      is a standing argument against adding nationalities speculatively.
#      This corpus is arts- and food-heavy: "Greek yogurt", "Italian restaurant",
#      "French doors", "Turkish coffee" are all live risks.
#
# Add a nationality only when it has an ACTUAL served-population occurrence in
# the data, never pre-emptively.
#
# NOTE for any future expansion: entries with a directional prefix must be
# matched LONGEST-FIRST. "south sudan" maps to Southern and East African but
# "sudan" maps to North African, so a naive substring match assigns South
# Sudanese people to the wrong region entirely. Same trap for
# "equatorial guinea"/"guinea" and "north korea"/"korea".
# ============================================================
EXCLUDED_NATIONALITY_TERMS = frozenset({
    "english", "polish", "spanish", "portuguese",   # homographs / language names
    "chad", "turkey", "georgia", "jordan", "oman",  # homographs: names & places
    "mongolian", "greek", "italian", "french",      # commonly modify objects/cuisine/art
})

# ============================================================
# CASES 6 & 7 — Country/nationality NOT in taxonomy
# Covers both "Jamaican" (nationality) and "from Jamaica" (Case 7)
# ============================================================
COUNTRY_REGION_MAP = {
    "jamaican": ("Caribbean Origins", "", ""),
    "jamaica": ("Caribbean Origins", "", ""),
    "trinidadian": ("Caribbean Origins", "", ""),
    "trinidad": ("Caribbean Origins", "", ""),
    "barbadian": ("Caribbean Origins", "", ""),
    "barbados": ("Caribbean Origins", "", ""),
    "haitian": ("Caribbean Origins", "", ""),
    "haiti": ("Caribbean Origins", "", ""),
    "guyanese": ("Caribbean Origins", "", ""),
    "guyana": ("Caribbean Origins", "", ""),
    "brazilian": ("Latin, Central, and South American Origins", "", ""),
    "brazil": ("Latin, Central, and South American Origins", "", ""),
    "colombian": ("Latin, Central, and South American Origins", "", ""),
    "colombia": ("Latin, Central, and South American Origins", "", ""),
    "mexican": ("Latin, Central, and South American Origins", "", ""),
    "mexico": ("Latin, Central, and South American Origins", "", ""),
    "salvadoran": ("Latin, Central, and South American Origins", "", ""),
    "el salvador": ("Latin, Central, and South American Origins", "", ""),
    "guatemalan": ("Latin, Central, and South American Origins", "", ""),
    "guatemala": ("Latin, Central, and South American Origins", "", ""),
    "peruvian": ("Latin, Central, and South American Origins", "", ""),
    "peru": ("Latin, Central, and South American Origins", "", ""),
    "venezuelan": ("Latin, Central, and South American Origins", "", ""),
    "venezuela": ("Latin, Central, and South American Origins", "", ""),
    "indian": ("Asian Origins", "South Asian Origins", "Indian (India)"),
    "india": ("Asian Origins", "South Asian Origins", "Indian (India)"),
    "kerala": ("Asian Origins", "South Asian Origins", "Indian (India)"), # state in India, often named directly e.g. "Kerala Cultural Association"
    "uyghur": ("Asian Origins", "West and Central Asian and Middle Eastern Origins", ""),
    "kyrgyz": ("Asian Origins", "West and Central Asian and Middle Eastern Origins", ""),
    "kyrgyzstan": ("Asian Origins", "West and Central Asian and Middle Eastern Origins", ""),
    "cameroonian": ("African Origins", "Central and West African Origins", ""), # no L3 entry for Cameroon -- falls to L2
    "cameroon": ("African Origins", "Central and West African Origins", ""),
    "sierra leone": ("African Origins", "Central and West African Origins", ""),
    "nigerian": ("African Origins", "Central and West African Origins", ""), # safety net -- if "Nigerian" is a real L3 entry in the taxonomy, that match wins anyway via depth priority
    "nigeria": ("African Origins", "Central and West African Origins", ""),
    "ghana": ("African Origins", "Central and West African Origins", ""),
    "djibouti": ("African Origins", "Southern and East African Origins", ""),
    "djiboutian": ("African Origins", "Southern and East African Origins", ""),
    "namibia": ("African Origins", "Southern and East African Origins", ""),
    "namibian": ("African Origins", "Southern and East African Origins", ""),
    "botswana": ("African Origins", "Southern and East African Origins", ""),
    "botswanan": ("African Origins", "Southern and East African Origins", ""),
    "zimbabwe": ("African Origins", "Southern and East African Origins", ""),
    "zimbabwean": ("African Origins", "Southern and East African Origins", ""),
    "mozambique": ("African Origins", "Southern and East African Origins", ""),
    "mozambican": ("African Origins", "Southern and East African Origins", ""),
    # --- Added 2026-07-21, evidence-driven (see EXCLUDED_NATIONALITY_TERMS below).
    # A bulk expansion of ~200 nationalities was built and measured over all 448
    # rows first: it produced 0 fixes and 4 regressions, so only terms with an
    # ACTUAL occurrence in the corpus were kept. These three had one:
    #   eritrean  -- 5 uses, all served-population ("Ethiopian and Eritrean youth").
    #                Without it a row naming both collapses to the Ethiopian L3
    #                and silently drops Eritrean; with it, two sub-groups compete
    #                and the resolver correctly rolls up to the L2 region.
    #   congolese -- 1 use, served-population ("5 canadians 5 congolese 5 ivorians").
    #                Bare "congo" is deliberately NOT added: unlike the demonym it
    #                reads as a geographic reference ("our work in Congo"), which
    #                is not an Edmonton served population.
    #   oromo/oromian -- an ethnic group within Ethiopia, not a country, so it can
    #                never come from a country list; carried only by the org name
    #                ("Foundation for Oromian Culture"). "oromian" is the form that
    #                actually appears -- "oromo" is added as the standard demonym.
    "eritrean": ("African Origins", "Southern and East African Origins", ""),
    "eritrea": ("African Origins", "Southern and East African Origins", ""),
    "congolese": ("African Origins", "Central and West African Origins", ""),
    "oromo": ("African Origins", "Southern and East African Origins", ""),
    "oromian": ("African Origins", "Southern and East African Origins", ""),
    "ghanaian": ("African Origins", "Central and West African Origins", ""),
    "sierra leonean": ("African Origins", "Central and West African Origins", ""),
    "egyptian": ("African Origins", "North African Origins", ""),
    "africancanadian": ("African Origins", "", ""), 
    "gazan": ("Asian Origins", "West and Central Asian and Middle Eastern Origins", "Palestinian"),
    "gaza": ("Asian Origins", "West and Central Asian and Middle Eastern Origins", "Palestinian"),
}

# =======================
# CASE 9 — BIPOC keywords 
# =======================
BIPOC_KEYWORDS = [
    r"\bbipoc\b",
    r"\bqtbipoc\b",
    r"\bpoc\b",
    r"\bibpoc\b",
    r"\bpeople of colou?r\b",
    #r"\bblack african\b",
    #r"\bracialized\b", # Change to flag if "racialized" is detected
]

# When a BIPOC/POC keyword is IMMEDIATELY followed by a funding/program noun,
# it is naming the grant/program ("the BIPOC Grant will support...", "a BIPOC
# Media Lab") rather than describing a served population -- so that occurrence
# is NOT a real BIPOC target (is_bipoc_real_target skips it, exactly like the
# example/negation guards). A genuine "BIPOC youth / women / artists /
# communities / entrepreneurs" mention elsewhere still counts.
BIPOC_PROGRAM_NAME_AFTER_PATTERNS = [
    r"^[\s\-]*(grant|fund|funding|program|programme|media\s+lab|lab|initiative|"
    r"stream|cohort|bursary|scholarship|residenc(?:y|ies)|award|prize|pathway)s?\b",
]

# Over-broad continent keyword that is used far more often in a non-ethnic
# geographic sense ("in the North American context/market") than as a served-
# population descriptor, and never resolves correctly on its own (the real
# Indigenous branch is keyed on "north american indigenous" and the specific
# nations/Métis/Inuit entries). build_taxonomy skips emitting it as a matchable
# keyword. NOTE: does NOT include "asian"/"african" etc. -- those ARE used as
# real served-group descriptors ("Asian community", "African youth").
TAXONOMY_KEYWORD_STOPLIST = {"north american"}

# ============================================================
# CASE 9b — Broad identity labels (not in taxonomy directly)
# Black/Jewish/Arab removed -- these are real Level 2 entries under
# "Other Ethnic and Cultural Origins" in the taxonomy, matched through
# find_taxonomy_matches() instead of here now.
# ============================================================
BROAD_IDENTITY_KEYWORDS = [
    # "hispanic" removed — real L2 taxonomy keyword under "Latin, Central, and South American Origins";
    # keeping it here caused taxonomy + broad-identity to produce two different L1s → spurious Multiple.
    # Same fix already applied to Black/Jewish/Arab (see comment above).
    # "latino"/"latina"/"latinx" removed — moved to PATTERN_RULES with the correct L1.
    r"\bmixed heritage\b",
    r"\bmixed race\b",
    r"\bmultiracial\b",
    r"\bmulti[\-\s]ethnic\b",
]

# Afro-Caribbean / Afro-Latino name TWO distinct Level 1 groups at
# once -> always Multiple, regardless of anything else in the text.
ALWAYS_MULTIPLE_COMPOUNDS = {
    r"\bafro[\-\u2010\u2011\u2012\u2013\u2014\s]*caribbean\b": (
        ("African Origins", "", ""),
        ("Caribbean Origins", "", ""),
    ),
    r"\bafro[\-\u2010\u2011\u2012\u2013\u2014\s]*latin(o|a|x)?\b": (
        ("African Origins", "", ""),
        ("Latin, Central, and South American Origins", "", ""),
    ),
    r"\bbyzantine\b": (
        ("European Origins", "", ""),
        ("Asian Origins", "West and Central Asian and Middle Eastern Origins", ""),
    ),
}

# Words that, on their own, should NOT trigger BIPOC/Multiple classification
# unless paired with an actual ethnic 'hint'. Handled separately from
# BIPOC_KEYWORDS because the rule is different (Case 11).
# Always flagged for review either way now (signal or no signal) --
# see check_grassroots_case().

AMBIGUOUS_EQUITY_WORDS = [
    #r"\bmarginalized\b", # Can be removed because marginalized can also refer to gender 
    #r"\bgrassroots\b", # Can be removed
    #r"\bethnocultural\b",
    r"\bracialized\b",
    #r"\bunderrepresented\b", # Possible to overlook as most times refers to gender and sexual identity
    #r"\bmulticultural\b",
    #r"\bdiverse\b",
    #r"\brefugee\b",
    #r"\bimmigrant\b",
    #r"\bfrancophone\b",
    #r"\bnewcomer\b", # Can be overlooked
    #r"\bculturally\b",
    r"\bminorit(y|ies)\b",
]

# =========================================================
# CASE 10 — Known organization name -> ethnicity lookup
# Only consulted as a LAST RESORT if classification would
# otherwise be General Population.
# ========================================================
ORG_NAME_ETHNICITY_MAP = {
    "bent arrow": ("North American Indigenous Origins", "", ""),
    "treaty 6": ("North American Indigenous Origins", "", ""), # Flag for review, as "Treaty 6" could refer to the geographic region (which would be L1 or L2) rather than the organization (which would be Case 10). Only trigger if "Treaty 6" appears in the funding request name or purpose, not just the description.
    "niginan housing ventures": ("North American Indigenous Origins", "", ""),
    # Stakeholder ruling (2026-07-21): this centre predominantly serves the
    # Chinese community. Deliberately curated as a WHOLE-ORG-NAME entry rather
    # than by teaching the extractors the word "Chinatown" -- "Chinatown" alone
    # is a NEIGHBOURHOOD, not an ethnic signal, and must not classify on its own
    # (e.g. a separate row about greening Chinatown's public realm serves that
    # district's residents and businesses generally, and correctly stays
    # General). Keying the full org name gets this row right without making the
    # place name a trigger anywhere else.
    "edmonton chinatown multicultural centre": ("Asian Origins", "East and Southeast Asian Origins", "Chinese"),
    "the shaama centre for seniors and women": ("Asian Origins", "South Asian Origins", ""),
}

# ============================================================
# G1 step 2 — Served-frame rescue patterns.
#
# An identity term sitting in one of these explicit "who is served" frames
# IS the served population, even if it also happens to echo the org's own
# name, or follows historical/expansion framing, elsewhere in the same
# text. This precedence check runs BEFORE the org-name-echo demotion in
# infer_role() -- e.g. an "<Ethnicity> Cultural Society ... serves the
# <Ethnicity> community" must keep that term as served despite it also
# appearing in the org's own name.
# ============================================================
SERVED_FRAME_BEFORE_PATTERNS = [
    r"\bfor\s*(?:the\s+)?$",
    r"\bserving\s*(?:the\s+)?$",
    r"\bserves?\s*(?:the\s+)?$",
]

SERVED_FRAME_CONTINUATION_PATTERNS = [
    r"\bcontinues?\s+today\b",
    r"\bcontinues?\s+to\s+serve\b",
]

# ============================================================
# A silent-body org name that contains ONLY a religion or language signal
# (no real ethnic/country/pattern term) stays General Population + a
# targeted flag, rather than guessing an ethnicity from an ambiguous
# religious or linguistic marker (e.g. "Islamic Association",
# "French Canadian Association" -- language service, not necessarily
# French ethnic identity).
# ============================================================
SILENT_NAME_RELIGION_PATTERN = r"\b(islamic|muslim|hindu|sikh|church)\b"
SILENT_NAME_LANGUAGE_PATTERN = r"\b(french|francophone)\b"

# ============================================================
# Context-override / historical / negation / aspirational / example
# phrase banks — all generic, applied to ANY keyword (not group-specific)
# ============================================================
EXPANSION_PHRASES = [
    r"beyond (its|their|our|the) (original|previous|former|initial|traditional|historic(al)?)",
    r"expanding beyond",
    r"expansion",
    r"not (exclusively|solely|limited to|just|restricted to)",
    r"no longer (limited|restricted|focused|exclusively)",
    r"open(ing)? (up )?to (all|broader|wider|diverse|other)",
    r"(increasingly|more) diverse",
    r"welcom(es?|ing) (all|everyone|anyone|diverse)",
    r"regardless of (ethnic|cultural|racial|background)",
    r"all (cultural|ethnic|racial)? backgrounds",
    r"without regard to",
    r"irrespective of",
    r"inclusive of all",
]
IDENTITY_EXPANSION_DISCLAIMER_PATTERNS = [
    r"beyond (its|their|our|the) (original|previous|former|initial|traditional|historic(al)?)",
    r"no longer (limited|restricted|focused|exclusively)",
    r"not (exclusively|solely|limited to|just|restricted to) (?:serving |for |focused on )?(?:the )?[a-z]",
]

HISTORICAL_PHRASES = [
    r"historic(al(ly)?)?",
    r"former(ly)?",
    r"previous(ly)?",
    r"original(ly)?",
    r"(in|during) the past",
    r"used to (serve|focus|target|support)",
    r"once (served|focused|targeted|supported)",
    r"(its|their|our) roots (in|with)",
    r"founded (to serve|for|by)",
    r"(was|were) (established|created|founded) (for|to serve)",
]

NEGATION_PHRASES = [
    r"not (target(ing)?|serv(ing|e)|focus(ing|ed)|for|limited to|exclusively)",
    r"does not (target|serve|focus|support|cater)",
    r"do not (target|serve|focus|support|cater)",
    r"no longer (target(ing)?|serv(ing|e)|focus(ing|ed))",
    r"exclud(es?|ing)",
    r"except(ing)?",
    #r"other than",
    #r"outside of",
    r"not the (primary|main|sole|only) (focus|target|group|population)",
]

# Pruned negation list used ONLY by the ethnic annotation flag (extract_context_signals).
# The full NEGATION_PHRASES stays intact for is_negated() (gender/sex + ethnic candidate
# dropping). Drops the context-free offenders (exclud/except) and the "not for" branch
# that fires on "not-for-profit".
ETHNIC_ANNOTATION_NEGATION_PHRASES = [
    r"not (target(ing)?|serv(ing|e)|focus(ing|ed)|limited to|exclusively)",
    r"does not (target|serve|focus|support|cater)",
    r"do not (target|serve|focus|support|cater)",
    r"no longer (target(ing)?|serv(ing|e)|focus(ing|ed))",
    r"not the (primary|main|sole|only) (focus|target|group|population)",
]

ASPIRATIONAL_PHRASES = [
    r"hop(es?|ing) to (serve|reach|support|engage|include|target)",
    r"plan(s|ning) to (serve|reach|support|engage|include|target)",
    # "support" dropped from this alternation:
    # "aims to support X" is ordinary present-tense mission language (what
    # the org does), not a future/not-yet-achieved reach claim like "aims to
    # expand/reach/include" — treating it as aspirational was over-firing
    # and demoting genuinely-served groups to General. "will serve" bare
    # (no intervening adverb) was checked and is NOT matched by any pattern
    # here (line below requires eventually/soon/begin to/start to) — no
    # change needed for that half of item 6.
    r"aim(s|ing) to (serve|reach|engage|include|target|expand to)",
    r"intend(s|ing) to",
    r"will (eventually|soon|begin to|start to) (serve|reach|support)",
    r"goal(s)? (is|are|of|to) (reach(ing)?|serv(ing|e)|includ(ing|e))",
    r"aspir(es?|ing) to",
    r"seek(s|ing) to (expand|reach|grow|include)",
    r"in the future",
    r"(future|upcoming) (focus|programming|initiative)",
    r"wants? to (serve|reach|support|engage|include|target|expand)",
    # "hoping to [verb] its/their reach" -- a reach-expansion claim, not a
    # description of who is currently served.
    r"hop(es?|ing) to \w+ (its|their|the|this) reach\b",
]

# Same aspirational-reach frames as ASPIRATIONAL_PHRASES,
# but checked against a WIDER before-window (see infer_role) because the
# lead verb ("wants to"/"hoping to") can sit further back than the standard
# 60-char window when a row restates the same aspirational goal across two
# columns (Final_Summary_Description then Purpose) that get concatenated
# with only a single space between them.
ASPIRATIONAL_WIDE_WINDOW = 130

EXAMPLE_PHRASES = [
    r"such as",
    r"for example",
    r"e\.g\.?",
    r"i\.e\.?",
    r"includ(ing|e) (communities|groups|populations|organizations|people)? ?(such as|like)",
    r"like (the )?following",
    r"among (others|other groups|other communities)",
    r"(and|or) (other|similar) (communities|groups|populations)",
    r"compar(ed|ing) to",
    r"as (opposed|compared) to",
]

# Words suggesting an ethnic term names a CONSULTED PARTY (expert/
# advisor role) rather than the population served, e.g. "...consult
# wildlife biologists, conservation experts, and indigenous knowledge
# holders". Never suppresses a match -- only adds a flag, since there's
# no reliable way to confirm this either way.
EXPERT_ROLE_PHRASES = [
    r"\bexperts?\b",
    r"\bspecialists?\b",
    r"\bconsultants?\b",
    r"\badvisors?\b",
    r"\bpractitioners?\b",
    r"\bknowledge holders?\b",
    r"\bstakeholders?\b",
    r"\bbiologists?\b",
]

SERVING_CONTEXT_WORDS = [
    r"\bserve(s|d)?\b",
    r"\bserving\b",
    r"\bpopulation\b",
    #r"\bcommunit(y|ies)\b",
    r"\bdemographic(s)?\b",
    r"\bfocus(ed|es)?\b",
    r"\btarget(ed|ing)?\b",
    r"\breach\b",
    r"\bbeneficiar(y|ies)\b",
    #r"\bclientele\b",
    #r"\bmembership\b",
    #r"\bmembers\b",
    #r"\baudience\b",
    #r"\bclients\b",
    ##r"\bgroups\b",
]

# =============================================================================
# Phase 2 — Evidence-role frames
#
# Weak roles: a matched identity term surrounded by one of these frames
# describes an ORG NAME or a SERVICE PROVIDER, not the served population.
# example/aspirational/negated reuse the phrase banks above. Anything that
# matches none of these frames defaults to "served" (strong).
# =============================================================================
ROLE_ORG_NAME_BEFORE_PATTERNS = [
    r"\bin partnership with\s*$",
    r"\bin collaboration with\s*$",
    r"\btogether with\s*$",
    r"\bpresented by\s*$",
]

ROLE_ORG_NAME_AFTER_PATTERNS = [
    
    r"^\s*(?:\w+\s+){0,3}(?:institutes?|associations?|societ(?:y|ies)|centres?|centers?|"
    r"foundations?|councils?|collaboratives?|coalitions?|clubs?|networks?|groups?|"
    r"compan(?:y|ies)|troupes?|theatres?|theaters?|ballets?)\b",
]

ROLE_PROVIDER_BEFORE_PATTERNS = [
    r"\bled by\s*$",
    r"\bdelivered by\s*$",
    r"\bfacilitated by\s*$",
    r"\b(?:consultants?|advisors?|liaisons?)\s+to\s+(?:integrate|apply|bring|incorporate|share)\s*$",
]

ROLE_PROVIDER_AFTER_PATTERNS = [
    # Anchored — same bleed-prevention reasoning as ROLE_ORG_NAME_AFTER_PATTERNS.
    # NOTE: deliberately excludes "elder(s)" -- unlike the other nouns here,
    # "elder" is at least as commonly a SERVED-population noun ("support for
    # Indigenous elders") as a provider-role noun ("led by an Elder"), so it's
    # too ambiguous to use as a standalone weak-role signal.
    r"^\s*(?:\w+\s+){0,2}(?:nutritionists?|dietitians?|professionals?|"
    r"facilitators?|instructors?|advisors?|consultants?|artists?|"
    r"teachers?|liaisons?)\b",
]

# ============================================================
# Allyship / reconciliation-ally frame demotion
#
# An "ally to indigenous people"-style frame names the ORG/SPEAKER's
# relationship to a group, not the group as a served population
# ("...an opportunity to be an ally to indigenous people
# ============================================================
ROLE_ALLYSHIP_BEFORE_PATTERNS = [
    r"\ban ally to\b",
    r"\ballies of\b",
    r"\ballyship (with|for|to)\b",
    r"\bin support of reconciliation\b",
    r"\b(contribute|committed?) to reconciliation\b",
]

ROLE_TOPIC_AFTER_PATTERNS = [
    r"^\s*(?:\w+\s+){0,2}perspectives?\b",
    r"^\s*(?:\w+\s+){0,3}knowledge\s+holders?\b",
]

ROLE_SETTING_BEFORE_PATTERNS = [
    r"\bbased on\b",
    r"\binspired by\b",
    r"\b(?:the\s+)?(?:tale|story|myth|legend)s?\s+(?:of|about)\b",
    r"\bset in\b",
    r"\bdepicting\b",
]

ROLE_SETTING_AFTER_PATTERNS = [
    # Term followed BY the story/tale/myth/legend noun, not just preceded
    # by it (e.g. "an Egyptian STORY about a Prince..." -- "story about" 
    r"^\s*(?:\w+\s+){0,1}(?:tale|story|myth|legend)s?\s+(?:of|about)\b",
]

# Bare "a [X] festival" is too broad to use as a GENERIC setting, so "Byzantine ... Festival" is reliably a
# themed/branded event name in this dataset
BYZANTINE_FESTIVAL_AFTER_PATTERN = r"^\s*(?:\w+\s+){0,2}festival\b"

# ============================================================
# A taxonomy keyword that ALSO has an unrelated, common non-ethnic sense
# ("polish" as in "final polish" on a video edit, not the Polish people)
# is skipped entirely at THIS occurrence -- not merely weak-tagged, since
# there is no ethnic identity claim of any kind here to flag for review.
# Keyed by the bare taxonomy keyword; checked against the ~20-char text
# immediately before the match (see extract_taxonomy_candidates).
# ============================================================
NON_ETHNIC_SENSE_BEFORE_PATTERNS = {
    "polish": [r"\b(?:final|last|finishing|rough)\s*$"],
}

# ============================================================
# Indigenous topic-content / partnership:
# ============================================================
ROLE_TOPIC_KEEP_AFTER_PATTERNS = [
    r"^\s*(?:\w+\s+){0,2}(?:knowledge|wisdom|dance|art|teachings?|ways\s+of\s+knowing)\b",
    r"^\s*(?:\w+\s+){0,2}(?:nations?\s+)?engagement\b",
]

ROLE_TOPIC_KEEP_BEFORE_PATTERNS = [
    r"\bin\s+partnership\s+with\b",
    r"\bin\s+collaboration\s+with\b",
    r"\bcollaboration\s+with\b",
    r"\bpartner(?:ing|ships?)?\s+with\b",
    r"\bengagement\s+with\b",
    r"\balongside\b",
    r"\bwork(?:ing)?\s+with\b",
]

INDIGENOUS_CONTEXT_RESCUE_PATTERNS = [
    r"\bresidential school",
    r"\btruth and reconciliation\b",
    r"\bceremon(y|ies)\b",
]

"""
-- Not Necessary to be handled right now for processing sakes.

# Common typos / nationality-vs-canonical-term variants.
KEYWORD_ALIASES = {
    "somalian": "somali",
    "ethopian": "ethiopian",
    "ethipian": "ethiopian",
    "rwandese": "   ndan",
    "congolaise": "congolese",
    "congolais": "congolese",
    "mozambiquean": "mozambican",
    "tanzanean": "tanzanian",
    "ugandese": "ugandan",
    "burundaise": "burundian",
    "filippino": "filipino",
    "phillipine": "filipino",
    "philippine": "filipino",
    "viet": "vietnamese",
    "indo-canadian": "south asian",
    "indo canadian": "south asian",
    "south-asian": "south asian",
    "middle eastern": "west and central asian and middle eastern",
    "middle-eastern": "west and central asian and middle eastern",
}
"""

IDENTITY_PHRASE_REWRITES = [
    # "black african/africans" masked to "african" so the bare "black" token is consumed
    # and does not trigger the is_black path; the phrase resolves through African Origins
    # via the umbrella-drop rule in resolver 
    (r"\bblack africans?\b",    "african"),
    # "african canadian/canadians" masked to a synthetic token so bare "african" cannot re-match;
    # "africancanadian" resolves to African Origins via COUNTRY_REGION_MAP 
    (r"\bafrican canadians?\b", "africancanadian"),
    (r"\bafrican american\b",   "black"),
    (r"\black american\b",      "black"),
    (r"\black canadian\b",      "black"),
]

# Directional/regional qualifiers that prevent the African Canadian/American
# identity rewrite from swallowing phrases like "East African Canadian".
DIRECTIONAL_AFRICAN_PREFIXES = ["north", "south", "east", "west", "central", "saharan"]

# Common suffix patterns that appear in ethnic demonyms (Kenyan, Chinese, Danish…).
DEMONYM_SUFFIXES = ["an", "ian", "ese", "ish", "ic", "ali", "i"]

# Words that almost certainly indicate a non-ethnic organization name leading token.
# Used by looks_like_demonym() in ethnic_taggerv3.py to gate Case 13.
NON_ETHNIC_LEADING_WORDS = {
    "soccer", "basketball", "hockey", "football", "tennis", "volleyball", "badminton",
    "cricket", "rugby", "swimming", "cycling", "chess",
    "youth", "women", "men", "senior", "seniors", "children", "adult", "adults",
    "arts", "music", "dance", "theatre", "drama", "literary",
    "health", "wellness", "mental", "nutrition",
    "education", "learning", "training",
    "business", "professional", "entrepreneurs",
}

# =================================================
# CASE 13 — Potential Ethnocultural Organization Name
#
# Safety-net detector for unknown ethnocultural org names in the
# Funding Request Name column.  Only fires when Engine 1 produced zero
# candidates and BIPOC is absent — i.e. the row would otherwise fall
# through to General Population with no ethnic signal at all.
#
# NEVER classifies. NEVER overrides. Review flag only.
# =================================================

# Only the explicit "cultural" org forms remain. The bare "association",
# "community association", and "community organization" patterns were too broad
CASE_13_PATTERNS = [
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+association\b",
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+group\b",
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+society\b",
]

# ============================================================
# P2-1 — French/francophone language accommodation 
#
# When text matches LANGUAGE_ACCOMMODATION_PATTERNS but NOT
# FRENCH_ETHNIC_KEEP_PATTERNS, French/European ethnic candidates
# are dropped and an annotation flag is emitted instead.
# ============================================================
LANGUAGE_ACCOMMODATION_PATTERNS = [
    r"\bfrench[- ]speaking\b",
    r"\bin (both )?(french and english|english and french)\b",
    r"\b(both )?french and english\b",
    r"\bofficial[- ]language minority\b",
    r"\bfrancophone\b",
]

FRENCH_ETHNIC_KEEP_PATTERNS = [
    r"\bfrench canadian association\b",
    r"\bfrancophone cultural\b",
    r"\bfrench heritage\b",
    r"\bfrench cultural\b",
]