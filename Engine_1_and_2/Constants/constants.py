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

# North American Indigenous umbrella-widening rule (resolver Step 4a)
INDIGENOUS_L1 = "North American Indigenous Origins"
INDIGENOUS_UMBRELLA_FLAG = (
    "Review: Indigenous umbrella term co-occurs with specific sub-group(s) - "
    "classified at general North American Indigenous level; verify served population"
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
    (r"\btreaty 6\b", "North American Indigenous Origins", "", ""),
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
    "ghanaian": ("African Origins", "Central and West African Origins", ""),
    "sierra leonean": ("African Origins", "Central and West African Origins", ""),
    "egyptian": ("African Origins", "North African Origins", ""),
    "africancanadian": ("African Origins", "", ""),  # injected by IDENTITY_PHRASE_REWRITES mask — see P1-1
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
    # Add more known organization name -> ethnicity mappings here as identified.
    # NOTE: this map is a tiny curated last resort ONLY -- do not add more
    # per-org entries. Plan.md Chunk G1 step 5's generalizable silent-body
    # name rule (see classify_pipeline.classify_from_raw_name) covers
    # unknown orgs generically and is the correct place for new coverage.
}

# ============================================================
# G1 step 2 — Served-frame rescue patterns.
#
# An identity term sitting in one of these explicit "who is served" frames
# IS the served population, even if it also happens to echo the org's own
# name, or follows historical/expansion framing, elsewhere in the same
# text. This precedence check runs BEFORE the org-name-echo demotion in
# infer_role() -- e.g. "Somali Canadian Cultural Society ... serves the
# Somali community" must keep Somali as served despite "Somali" also
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
# G1 step 5 — Generalizable silent-body name rule: exclusions.
#
# A silent-body org name that contains ONLY a religion or language signal
# (no real ethnic/country/pattern term) stays General Population + a
# targeted flag, rather than guessing an ethnicity from an ambiguous
# religious or linguistic marker (e.g. "Islamic Missionary Association",
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
    r"aim(s|ing) to (serve|reach|support|engage|include|target)",
    r"intend(s|ing) to",
    r"will (eventually|soon|begin to|start to) (serve|reach|support)",
    r"goal(s)? (is|are|of|to) (reach(ing)?|serv(ing|e)|includ(ing|e))",
    r"aspir(es?|ing) to",
    r"seek(s|ing) to (expand|reach|grow|include)",
    r"in the future",
    r"(future|upcoming) (focus|programming|initiative)",
]

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
# Phase 2 — Evidence-role frames (Plan.md Fix 1 Phase 2)
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
    # Anchored to the start of the "after" window with a small filler-word
    # allowance, so this can't bleed forward into an unrelated later mention
    # (e.g. a second, provider-framed occurrence of the same keyword further
    # down the sentence).
    r"^\s*(?:\w+\s+){0,3}(?:institute|association|society|centre|center|"
    r"foundation|council|collaborative|coalition|club|network|group|"
    r"company|troupe|theatre|theater|ballet)\b",
]

ROLE_PROVIDER_BEFORE_PATTERNS = [
    r"\bled by\s*$",
    r"\bdelivered by\s*$",
    r"\bfacilitated by\s*$",
]

ROLE_PROVIDER_AFTER_PATTERNS = [
    # Anchored — same bleed-prevention reasoning as ROLE_ORG_NAME_AFTER_PATTERNS.
    # NOTE: deliberately excludes "elder(s)" -- unlike the other nouns here,
    # "elder" is at least as commonly a SERVED-population noun ("support for
    # Indigenous elders") as a provider-role noun ("led by an Elder"), so it's
    # too ambiguous to use as a standalone weak-role signal.
    r"^\s*(?:\w+\s+){0,2}(?:nutritionists?|dietitians?|professionals?|"
    r"facilitators?|instructors?|advisors?|consultants?|artists?|"
    r"teachers?)\b",
]

# ============================================================
# G3 — Indigenous pattern-path role-tiering (Plan.md Chunk G3).
#
# Indigenous PATTERN candidates ("indigenous"/"aboriginal"/"metis"/etc,
# matched via PATTERN_RULES) already flow through infer_role like any
# other candidate (extract_pattern_candidates calls it), but two framings
# weren't covered by the existing provider/org_name weak-role frames
# above: a curriculum/awareness TOPIC being taught ("...teach eco-action
# strategies, and Indigenous perspectives") and a CONSULTED-PARTY mention
# ("consult wildlife biologists, conservation experts, and Indigenous
# knowledge holders"). Neither names the served population, so both get a
# new weak "topic" role here -- same mechanism as ROLE_PROVIDER/
# ROLE_ORG_NAME, just a new frame; see infer_role().
#
# Scoped narrowly to the exact nouns that actually appear in a topic/
# consultation frame (not a bare "knowledge"/"awareness" keyword), so this
# never catches a genuine served mention such as "Indigenous knowledge"
# (traditional healing services), "Indigenous Peoples Exhibit Tours", or
# "Indigenous Awareness Training" delivered ABOUT a served population --
# see the 50596/54528/50681/51620 regression rows, all of which must stay
# Indigenous.
# ============================================================
ROLE_TOPIC_AFTER_PATTERNS = [
    r"^\s*(?:\w+\s+){0,2}perspectives?\b",
    r"^\s*(?:\w+\s+){0,3}knowledge\s+holders?\b",
]

# G3 — served-frame rescue extension (used alongside SERVED_FRAME_BEFORE/
# CONTINUATION_PATTERNS in infer_role): residential-school / Truth-and-
# Reconciliation / ceremony context ANYWHERE in the body text is strong
# evidence that the Indigenous mention(s) in this row concern a genuinely
# served population (survivors of historical trauma, ceremony
# participants) even when the specific occurrence itself reads as staff-
# training/topic framing (e.g. "Indigenous Awareness Training" delivered
# to staff so they can better serve a population affected by residential
# schools -- row 51620). Checked text-wide, same mechanism as
# SERVED_FRAME_CONTINUATION_PATTERNS above.
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
    "rwandese": "rwandan",
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
    # via the umbrella-drop rule in resolver Step 4 (Fix 2).
    (r"\bblack africans?\b",    "african"),
    # "african canadian/canadians" masked to a synthetic token so bare "african" cannot re-match;
    # "africancanadian" resolves to African Origins via COUNTRY_REGION_MAP (P1-1).
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
# "community association", and "community organization" patterns were too broad —
# they matched generic non-ethnic orgs (Riverdale Community Association, Tenants
# Association, etc.) and produced 100% false positives on audit.
CASE_13_PATTERNS = [
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+association\b",
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+group\b",
    r"^([a-z][a-z\s\-']+?)\s+cultural\s+society\b",
]

# ============================================================
# P2-1 — French/francophone language accommodation (Issue H)
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