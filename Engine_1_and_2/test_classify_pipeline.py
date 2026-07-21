import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  

from classify_pipeline import classify_row, STAKEHOLDER_REVIEWED_COL
from ethnic_taggerv3 import MULTIPLE_ETHNIC, OTHER_ETHNIC, GENERAL_POP

"""
test_classify_pipeline.py
Regression tests for classify_pipeline.classify_row().

Run from the repo root:
    .venv\\Scripts\\python.exe -m pytest "Engine 1 and 2/test_classify_pipeline.py" -v
"""

# ---------------------------------------------------------------------------
# Minimal taxonomy fixture
#
# Sorted deepest-first, longest-first within the same depth — mirrors the
# order that build_taxonomy() produces so the resolver sees the same priority
# it would see in production.
#
# Only the keywords exercised by the test suite are included.  Real taxonomy
# rows not represented here (e.g. Hispanic, Black) are covered by the
# pattern rules and country map which are imported from ethnic_taggerv3
# at runtime.
# ---------------------------------------------------------------------------
TAXONOMY = [
    # depth 3 — specific groups (longest keyword first within depth)
    {
        "keyword": "filipino",
        "level1": "Asian Origins",
        "level2": "East and Southeast Asian Origins",
        "level3": "Filipino",
        "depth": 3,
    },
    {
        "keyword": "somali",
        "level1": "African Origins",
        "level2": "Southern and East African Origins",
        "level3": "Somali",
        "depth": 3,
    },
    {
        "keyword": "cree",
        "level1": "North American Indigenous Origins",
        "level2": "First Nations Origins",
        "level3": "Cree",
        "depth": 3,
    },
    {
        "keyword": "métis",
        "level1": "North American Indigenous Origins",
        "level2": "Métis",
        "level3": "",
        "depth": 2,
    },
    # depth 1 — broad categories (longest keyword first within depth)
    {
        "keyword": "indigenous",
        "level1": "North American Indigenous Origins",
        "level2": "",
        "level3": "",
        "depth": 1,
    },
    {
        "keyword": "caribbean",
        "level1": "Caribbean Origins",
        "level2": "",
        "level3": "",
        "depth": 1,
    },
    {
        "keyword": "african",
        "level1": "African Origins",
        "level2": "",
        "level3": "",
        "depth": 1,
    },
]


def row(desc="", summary="", purpose="", name=""):
    """Build a minimal mock input row from the four source columns."""
    return {
        "Final_Project_Description":  desc,
        "Final_Summary_Description":  summary,
        "Purpose":                    purpose,
        "Funding Request Name":       name,
    }


class TestClassifyPipeline(unittest.TestCase):

    # ------------------------------------------------------------------
    # 1. Single taxonomy match
    # ------------------------------------------------------------------
    def test_single_taxonomy_match(self):
        """
        A single L3 taxonomy keyword resolves to its full L1/L2/L3 path.
        No flag is emitted for a clean taxonomy match.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting the Somali community in Edmonton."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")

    # ------------------------------------------------------------------
    # 2. Multiple distinct taxonomy matches → MULTIPLE
    # ------------------------------------------------------------------
    def test_multiple_taxonomy_matches_produces_multiple(self):
        """
        Two signals from different L1 branches always produce MULTIPLE,
        regardless of depth.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Program serves both Somali and Filipino youth."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        # Fix 4: the generic "Review: multiple distinct groups detected"
        # string is dropped as noise — the Multiple classification says as
        # much on its own.
        self.assertEqual(flag, "")

    # ------------------------------------------------------------------
    # 3. Country mapping case
    # ------------------------------------------------------------------
    def test_country_mapping(self):
        """
        A demonym in COUNTRY_REGION_MAP (not in the taxonomy sheet)
        is resolved through the country extractor.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Serving Jamaican newcomers and their families."),
            TAXONOMY,
        )
        self.assertEqual(e1, "Caribbean Origins")
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("supplementary list", flag)

    # ------------------------------------------------------------------
    # 4. Pattern rule case
    # ------------------------------------------------------------------
    def test_pattern_rule_match(self):
        """
        A directional phrase ('East African') fires the pattern extractor.
        Depth-2 pattern wins over depth-1 bare 'african' taxonomy match.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Support for East African newcomers in the city."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "")
        self.assertIn("Regional phrase matched", flag)

    # ------------------------------------------------------------------
    # 5. Compound identity (Afro-Caribbean) → always MULTIPLE
    # ------------------------------------------------------------------
    def test_compound_afro_caribbean_produces_multiple(self):
        """
        A compound identity phrase expands to two distinct L1 candidates.
        The resolver's distinct-L1 check fires and returns MULTIPLE.
        The hyphen is stripped by normalize_text; the compound pattern
        matches via the \\s* span in ALWAYS_MULTIPLE_COMPOUNDS.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Programming for the Afro-Caribbean community."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        # Fix 4: generic "Review: multiple distinct groups detected" string dropped.
        self.assertEqual(flag, "")

    # ------------------------------------------------------------------
    # 6. BIPOC alone (no other ethnic signal)
    # ------------------------------------------------------------------
    def test_bipoc_alone(self):
        """
        BIPOC with no other ethnic keyword produces MULTIPLE with no primary
        flag (Plan.md Chunk G10 item 5: the bare "BIPOC signal detected"
        text was dropped as noise -- BIPOC-alone -> Multiple is unambiguous
        locked policy, same treatment as the G9 Step-2b removal). No
        specific group is named.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services designed for BIPOC youth in the community."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertNotIn("BIPOC signal detected", flag)

    # ------------------------------------------------------------------
    # 7. BIPOC alongside a specific taxonomy group
    # ------------------------------------------------------------------
    def test_bipoc_plus_specific_group_flagged_for_review(self):
        """
        BIPOC + a named group is ambiguous: the resolver flags it for
        manual review and names the co-present group in the flag text.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="BIPOC-focused services with a particular emphasis on Somali youth."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("BIPOC keyword alongside", flag)
        self.assertIn("African Origins", flag)

    # ------------------------------------------------------------------
    # 8. Ambiguous equity word WITHOUT a paired ethnic signal
    # ------------------------------------------------------------------
    def test_grassroots_no_signal_produces_general_pop_with_note(self):
        """
        An AMBIGUOUS_EQUITY_WORD with no real ethnic signal resolves to
        General Population — it does NOT short-circuit classification
        before other evidence is weighed. Fix 4: the "Ambiguous equity term
        with no paired ethnic signal" note is dropped as noise; no flag.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="A multicultural community event for all residents."),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertEqual(flag, "")

    # ------------------------------------------------------------------
    # 9. Ambiguous equity word WITH a paired ethnic signal
    # ------------------------------------------------------------------
    def test_grassroots_with_signal_classifies_normally_and_flags(self):
        """
        An AMBIGUOUS_EQUITY_WORD alongside a real ethnic signal does NOT
        block classification — the signal wins. Fix 4: the "buzzword"
        note is dropped as noise; no flag.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="A multicultural program focused on the Somali community."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        self.assertEqual(flag, "")

    # ------------------------------------------------------------------
    # 10. Historical phrasing DOES NOT suppress classification
    #     AND is NOT surfaced as a production review flag (debug-only)
    # ------------------------------------------------------------------
    def test_historical_phrasing_does_not_change_classification(self):
        """
        Historical discourse markers were formerly a hard General Population
        override.  After the context-signal refactor they became annotation-only.
        After Change #1 they are DEBUG METADATA ONLY — not emitted in
        production flag output.

        CONTEXT DOES NOT AFFECT CLASSIFICATION OUTCOME.
        Historical framing is NOT a production review flag (alert fatigue).
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Historically serving the Somali community, this program continues today."),
            TAXONOMY,
        )
        # Must classify to the ethnic group, NOT fall back to General Population
        self.assertNotEqual(e1, GENERAL_POP)
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        # Historical framing is debug metadata — must NOT appear in production flag
        self.assertNotIn("Historical framing", flag)

    # ------------------------------------------------------------------
    # 11. Expansion phrasing DOES NOT suppress classification
    #     AND is NOT surfaced as a production review flag (debug-only)
    # ------------------------------------------------------------------
    def test_expansion_phrasing_does_not_suppress_classification(self):
        """
        Scope-expansion markers were formerly a hard General Population
        override.  After Change #1 they are DEBUG METADATA ONLY.

        CONTEXT DOES NOT AFFECT CLASSIFICATION OUTCOME.
        Expansion language is NOT a production review flag (alert fatigue).
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Expanding beyond its original focus on the Somali community to welcome all newcomers."),
            TAXONOMY,
        )
        self.assertNotEqual(e1, GENERAL_POP)
        self.assertEqual(e1, "African Origins")
        # Expansion context is debug metadata — must NOT appear in production flag
        self.assertNotIn("expansion", flag.lower())

    # ------------------------------------------------------------------
    # 12. Negation is annotation-only — extractor is a dumb sensor
    # ------------------------------------------------------------------
    def test_negation_is_annotation_only(self):
        """
        The extraction layer does NOT filter negated keywords — it is a
        dumb sensor.  Negation context is detected and annotated, but the
        ethnic signal still proceeds through the resolver.

        This validates the key architectural constraint:
        CONTEXT (including negation) MUST NEVER affect classification decisions.

        A human reviewer should check the flag and confirm intent.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="This program does not serve Somali clients exclusively but assists all newcomers."),
            TAXONOMY,
        )
        # Somali is still extracted by the dumb sensor — classification proceeds
        self.assertNotEqual(e1, GENERAL_POP)
        self.assertEqual(e1, "African Origins")
        self.assertIn("negation word", flag)

    # ------------------------------------------------------------------
    # 13. Organization name fallback (last resort)
    # ------------------------------------------------------------------
    def test_org_name_fallback(self):
        """
        When no taxonomy/pattern/country/compound signal is present,
        a known organization name resolves the row via last-resort lookup.
        Org lookup is name-only (Plan.md Chunk G1) -- real data always
        embeds the account name in the Funding Request Name column, not
        the body, so the token belongs in `name`, not `desc`.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Support through Bent Arrow programs for participants."),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("curated lookup list", flag)

    # ------------------------------------------------------------------
    # 14. Empty input → General Population with "Empty input" flag
    # ------------------------------------------------------------------
    def test_empty_input_returns_general_pop(self):
        """
        All four source columns empty → immediate General Population.
        No candidate extraction, no resolver call.
        """
        e1, e2, e3, flag = classify_row(row(), TAXONOMY)
        self.assertEqual(e1, GENERAL_POP)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertEqual(flag, "Empty input")


    # ------------------------------------------------------------------
    # 15. Unrecognized ethnocultural org name in title → review flag
    # ------------------------------------------------------------------
    def test_unrecognized_ethnocultural_org_title_is_flagged(self):
        """
        A Funding Request Name that matches an ethnocultural org name
        pattern (e.g. "Luhya Cultural Association") whose group identifier
        is not recognized by any extractor produces a review flag.

        Classification fallback is General Population — the org pattern
        does NOT infer ethnicity.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Luhya Cultural Association"),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("Potential ethnocultural organization name", flag)

    # ------------------------------------------------------------------
    # 16. Recognized group in title → no ethnocultural org flag
    # ------------------------------------------------------------------
    def test_recognized_group_in_org_title_not_flagged(self):
        """
        A group name that appears ONLY in the Funding Request Name (e.g.
        "Somali Cultural Association" — no body text) is a truly silent
        body. Plan.md Chunk G1 step 5's generalizable silent-body name rule
        classifies from that name instead of defaulting flat to General —
        always flagged for manual verification of the served population.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Somali Cultural Association"),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        self.assertIn("silent body", flag)

    # ------------------------------------------------------------------
    # 17. Guard clause: Case 13 skips when classification already exists
    # ------------------------------------------------------------------
    def test_ethnocultural_org_title_skipped_when_candidates_exist(self):
        """
        When Engine 1 produced ANY candidates (here: 'Somali' from the
        description), the Case 13 guard clause fires immediately and the
        ethnocultural org flag is NOT appended.

        Case 13 is strictly a last-resort safety net — it only fires when
        the row would otherwise produce General Population with no signal.
        The existing classification is preserved without noise.
        """
        e1, e2, e3, flag = classify_row(
            row(
                desc="Supporting the Somali community in Edmonton.",
                name="Luhya Cultural Association",
            ),
            TAXONOMY,
        )
        # Classification driven by "Somali" in description — unchanged
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        # Guard fired — Case 13 flag must NOT appear
        self.assertNotIn("Potential ethnocultural organization name", flag)

    # ------------------------------------------------------------------
    # Negation annotation: anchored + pruned (Part 2)
    # ------------------------------------------------------------------
    def test_not_for_profit_no_negation_flag(self):
        """'not-for-profit' with no ethnic term → General Pop, no negation flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="A trusted not-for-profit childcare centre serving families for years."),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertNotIn("negation word", flag)

    def test_excluded_inclusion_language_no_negation_flag(self):
        """'voices often excluded' (inclusion framing), no ethnic term → no negation flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Amplifying underrepresented voices often excluded from mainstream conversations."),
            TAXONOMY,
        )
        self.assertNotIn("negation word", flag)

    def test_excluded_near_term_pruned_no_negation_flag(self):
        """Ethnic term present but only benign 'excluded' → pruned, no negation flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Serving Somali families and amplifying voices often excluded."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertNotIn("negation word", flag)

    def test_intentional_negation_still_flags(self):
        """
        Real exclusion of a second group ('do not serve Filipino') → flag preserved.
        Negation is annotation-only (resolver.py never suppresses candidates on it), so
        both named groups still resolve to Multiple Ethnic — the flag is what matters here.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="We serve Somali families but do not serve Filipino newcomers."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("negation word", flag)

    # ------------------------------------------------------------------
    # Case 13 org-name flag: pruned to explicit "cultural" forms (Part 3)
    # ------------------------------------------------------------------
    def test_generic_community_association_not_flagged(self):
        """Generic community/association org titles no longer trigger Case 13."""
        for title in [
            "Riverdale Community Association",
            "Tenants Association",
            "Millwoods Community Organization",
        ]:
            e1, e2, e3, flag = classify_row(row(name=title), TAXONOMY_B2)
            self.assertNotIn("Potential ethnocultural organization name", flag)



# ---------------------------------------------------------------------------
# Sprint 2 taxonomy fixture (extends TAXONOMY with entries needed for new tests)
# ---------------------------------------------------------------------------
TAXONOMY_S2 = TAXONOMY + [
    {
        "keyword": "kenyan",
        "level1": "African Origins",
        "level2": "Southern and East African Origins",
        "level3": "Kenyan",
        "depth": 3,
    },
    {
        "keyword": "ethiopian",
        "level1": "African Origins",
        "level2": "Southern and East African Origins",
        "level3": "Ethiopian",
        "depth": 3,
    },
    {
        "keyword": "pakistani",
        "level1": "Asian Origins",
        "level2": "South Asian Origins",
        "level3": "Pakistani",
        "depth": 3,
    },
    {
        "keyword": "black",
        "level1": "Other Ethnic and Cultural Origins",
        "level2": "Black, not otherwise specified",
        "level3": "",
        "depth": 2,
    },
    {
        "keyword": "french",
        "level1": "European Origins",
        "level2": "Western European Origins",
        "level3": "French",
        "depth": 3,
    },
]


class TestSprint2Fixes(unittest.TestCase):
    """Regression tests for Sprint 2 classification fixes."""

    # ------------------------------------------------------------------
    # S1. African Canadians (plural) → African Origins
    # ------------------------------------------------------------------
    def test_african_canadians_plural_resolves_to_african_origins(self):
        """
        "african canadians" (plural) previously escaped the singular rewrite
        → bare "african" matched taxonomy → inconsistent with singular form.
        After P1-1 fix, both forms mask to "africancanadian" → African Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Advancement of African Canadians in Edmonton."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "")

    # ------------------------------------------------------------------
    # S2. African Canadian (singular) → African Origins (not Black)
    # ------------------------------------------------------------------
    def test_african_canadian_singular_resolves_to_african_origins(self):
        """After P1-1, "african canadian" no longer rewrites to black."""
        e1, e2, e3, flag = classify_row(
            row(desc="The organization supports the advancement of African Canadian communities."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")

    # ------------------------------------------------------------------
    # S3. African Canadian + Nigerian → Nigerian (country depth wins)
    # ------------------------------------------------------------------
    def test_african_canadian_plus_nigerian_resolves_to_nigerian(self):
        """
        "africancanadian" (depth 1) + "nigerian" (COUNTRY_REGION_MAP depth 2)
        → depth resolution picks Nigerian → Central and West African Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting African Canadian and Nigerian families in the city."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Central and West African Origins")

    # ------------------------------------------------------------------
    # Indigenous umbrella + specific sub-group → general L1 + review flag
    # ------------------------------------------------------------------
    def test_indigenous_umbrella_with_one_subgroup_narrows_not_widens(self):
        """
        Fix 9: exactly ONE distinct sub-group co-occurring with the
        'Indigenous' umbrella should narrow to that sub-group, not roll up
        to the general L1 (gold: PCC Prostate 'Indigenous men ... Métis
        Settlements' → Métis, not general Indigenous)."""
        e1, e2, e3, flag = classify_row(
            row(desc="Programs for Cree families and Indigenous youth in Edmonton."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "First Nations Origins")
        self.assertEqual(e3, "Cree")
        self.assertNotIn("Indigenous umbrella term co-occurs", flag)

    def test_indigenous_umbrella_with_metis_narrows_not_widens(self):
        """Fix 9: Métis (specific, accented) + 'Indigenous' (umbrella), only
        one distinct sub-group → narrows to Métis, no roll-up flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Celebrating the Métis Homeland and Indigenous artists at the festival."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "Métis")
        self.assertNotIn("Indigenous umbrella term co-occurs", flag)

    def test_indigenous_umbrella_with_two_subgroups_still_widens_and_flags(self):
        """Fix 9: TWO distinct sub-groups (Cree, Métis) + 'Indigenous' umbrella
        → genuinely ambiguous, still rolls up to general L1 + flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Programs for Cree and Métis families and Indigenous youth in Edmonton."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("Indigenous umbrella term co-occurs", flag)

    def test_metis_alone_stays_specific(self):
        """Sub-group with no umbrella word → stays specific, no new flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting Métis entrepreneurs and their families."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "Métis")
        self.assertNotIn("Indigenous umbrella term co-occurs", flag)

    def test_indigenous_umbrella_alone_no_flag(self):
        """Umbrella word with no sub-group → general L1, no new flag."""
        e1, e2, e3, flag = classify_row(
            row(desc="Serving Indigenous youth across the region."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "")
        self.assertNotIn("Indigenous umbrella term co-occurs", flag)

    # ------------------------------------------------------------------
    # S4. Indian + Pakistani → South Asian Origins (rollup, not Multiple)
    # ------------------------------------------------------------------
    def test_indian_and_pakistani_rolls_up_to_south_asian(self):
        """
        Two L3 candidates under South Asian Origins → P0-2 rollup → L2 South Asian.
        Must NOT produce Multiple Ethnic.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Serving Indian and Pakistani communities in Edmonton."),
            TAXONOMY_S2,
        )
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e1, "Asian Origins")
        self.assertEqual(e2, "South Asian Origins")

    # ------------------------------------------------------------------
    # S5. Kenyan + Ghanaian → African Origins L1 (different L2, same L1 rollup)
    # ------------------------------------------------------------------
    def test_kenyan_and_ghanaian_rolls_up_to_african_origins(self):
        """
        Kenyan (Southern/East) + Ghanaian (Central/West) → different L2s within
        African Origins → P0-2 rollup → African Origins L1, not Multiple.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="For African youth from diverse backgrounds including Kenyan and Ghanaian communities."),
            TAXONOMY_S2,
        )
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e1, "African Origins")

    # ------------------------------------------------------------------
    # S6. "Black African" alone → African Origins (Fix 2 rewrite)
    # ------------------------------------------------------------------
    def test_black_african_alone_resolves_to_african_origins(self):
        """
        Fix 2: r"\\bblack africans?\\b" is rewritten to "african" before
        extraction, so 'black' is never extracted separately.
        Result: African Origins (L1), not Multiple.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Programming for Black African newcomers in the city."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)

    # ------------------------------------------------------------------
    # S7. Somali + Black → Multiple, no primary flag
    # ------------------------------------------------------------------
    def test_somali_and_black_produces_multiple_no_generic_flag(self):
        """
        "Somali project for Black Muslim communities" — Somali (African Origins)
        + Black (Other Ethnic) → Multiple, no primary flag (Plan.md Chunk G9:
        the generic "multiple distinct groups detected" text is dropped as
        noise here too, same as Step 3's Fix 4 treatment — Black vs African
        is a locked policy call, not something needing a review flag).
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Somali project aims to strengthen cultural pride for Black Muslim communities."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertNotIn("umbrella term (Black)", flag)

    # ------------------------------------------------------------------
    # S8. Black + Indigenous → BIPOC signal (not "multiple distinct groups")
    # ------------------------------------------------------------------
    def test_black_and_indigenous_produces_bipoc_signal_flag(self):
        """
        Black + Indigenous together → P0-3 Part A fires → MULTIPLE_ETHNIC
        with "BIPOC signal detected", not "multiple distinct groups detected".
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Programs for Black and Indigenous youth in Edmonton."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("BIPOC signal detected", flag)
        self.assertNotIn("multiple distinct groups", flag)

    # ------------------------------------------------------------------
    # S9. Namibian demonym → African Origins (P1-2 demonym fix)
    # ------------------------------------------------------------------
    def test_namibian_demonym_resolves_to_african_origins(self):
        """
        "Namibian" was missing from COUNTRY_REGION_MAP. After P1-2 fix it
        resolves to African Origins / Southern and East African Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services for Namibian newcomers and their families."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertIn("supplementary list", flag)

    # ------------------------------------------------------------------
    # S10. "French Canadian Association" → ethnic kept (not language flag)
    # ------------------------------------------------------------------
    def test_french_canadian_association_keeps_ethnic_signal(self):
        """
        A named French org appearing ONLY in the name (no body text) is a
        truly silent body. Plan.md Chunk G1 step 5 explicitly EXCLUDES
        French/francophone as a name-only ethnic signal (too ambiguous
        with language-accommodation service orgs) -- General + a targeted
        exclusion note, not a French/European classification and not the
        generic "language accommodation" body-text note (that filter never
        runs here since there's no body candidate to filter).
        """
        e1, e2, e3, flag = classify_row(
            row(name="French Canadian Association of Alberta"),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("not an ethnic signal", flag)
        self.assertNotIn("language accommodation", flag)

    # ------------------------------------------------------------------
    # S11. "in French and English" + Indigenous → NOT Multiple due to French
    # ------------------------------------------------------------------
    def test_french_language_accommodation_drops_french_candidate(self):
        """
        "services in both French and English" is a language accommodation context.
        The French ethnic candidate should be dropped by the P2-1 filter,
        leaving only Indigenous → single ethnic result, not Multiple.
        Language accommodation annotation is emitted.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services are available in both French and English for Indigenous communities."),
            TAXONOMY_S2,
        )
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("language accommodation", flag)


# ---------------------------------------------------------------------------
# Step 4 umbrella-drop + deepest-shared-level tests (Fix 1)
# ---------------------------------------------------------------------------

class TestStep4UmbrellaDrop(unittest.TestCase):
    """Regression tests for the umbrella-drop / deepest-shared-level resolver rule."""

    # ------------------------------------------------------------------
    # F1. african(L1) + somali(L3,S&E) + ethiopian(L3,S&E)
    #     → drop umbrella, specifics share L2 → Southern & East African
    # ------------------------------------------------------------------
    def test_umbrella_dropped_specifics_share_l2(self):
        """
        bare 'african' (L1-only) is dropped as an umbrella when Somali and
        Ethiopian (both L3 under Southern & East African) are also present.
        The two L3s differ, but they share L2 → Southern & East African Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting African, Somali, and Ethiopian communities in Edmonton."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)

    # ------------------------------------------------------------------
    # F2. Somali(L3,S&E) + Ethiopian(L3,S&E) + East African(L2,S&E)
    #     → all share L2 → Southern & East African
    # ------------------------------------------------------------------
    def test_l3_and_l2_mixed_same_l2_rolls_up_to_l2(self):
        """
        East African is an L2-only pattern match (no L3); Somali and Ethiopian
        are L3. All three share L2 = Southern & East African Origins → return L2.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Serving Somali, Ethiopian, and East African newcomers."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)

    # ------------------------------------------------------------------
    # F3. Somali(S&E) + Ghanaian(C&W) → different L2 → African Origins L1
    # ------------------------------------------------------------------
    def test_different_l2_rolls_up_to_l1(self):
        """
        Somali (Southern & East) and Ghanaian (Central & West) share L1
        but differ at L2 → resolver returns African Origins L1 only.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Programming for Somali and Ghanaian youth in the community."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)

    # ------------------------------------------------------------------
    # F4. Black African + Kenyan + Ghanaian + Zimbabwean + South African
    #     → umbrella dropped, specifics span C&W and S&E → African Origins L1
    # ------------------------------------------------------------------
    def test_black_african_plus_multi_region_specifics_rolls_to_l1(self):
        """
        'Black African' is rewritten to 'african' (umbrella, L1-only).
        Kenyan and Zimbabwean → S&E; Ghanaian → C&W; South African → S&E.
        Umbrella dropped; specifics span two L2 regions → African Origins L1.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting Black African youth including Kenyan, Ghanaian, Zimbabwean and South African communities."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)


# ---------------------------------------------------------------------------
# Blueprint 2 taxonomy fixture (adds Kyrgyz, indigenous entries)
# ---------------------------------------------------------------------------
TAXONOMY_B2 = TAXONOMY_S2 + [
    {
        "keyword": "kyrgyz",
        "level1": "Asian Origins",
        "level2": "West and Central Asian and Middle Eastern Origins",
        "level3": "",
        "depth": 2,
    },
]


class TestBlueprint2Fixes(unittest.TestCase):
    """Regression tests for Blueprint 2 classification fixes."""

    # ------------------------------------------------------------------
    # B1. Kyrgyz → Asian Origins / West and Central Asian and Middle Eastern
    # ------------------------------------------------------------------
    def test_kyrgyz_resolves_to_west_central_asian(self):
        """
        'Kyrgyz' was added to COUNTRY_REGION_MAP and (above) to taxonomy fixture.
        Ensure it routes to the correct L2.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting Kyrgyz newcomer families in Edmonton."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "Asian Origins")
        self.assertEqual(e2, "West and Central Asian and Middle Eastern Origins")

    # ------------------------------------------------------------------
    # B2. Byzantine → Multiple (European + West Asian compound)
    # ------------------------------------------------------------------
    def test_byzantine_produces_multiple(self):
        """
        'Byzantine' was added to ALWAYS_MULTIPLE_COMPOUNDS mapping to
        European Origins AND Asian / West and Central Asian Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Programming for the Byzantine cultural heritage community."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)

    # ------------------------------------------------------------------
    # B3. Indigenous misspelling 'indiginous' → North American Indigenous
    # ------------------------------------------------------------------
    def test_indigenous_misspelling_indiginous_classifies(self):
        """
        Common misspelling 'indiginous' added to PATTERN_RULES.
        Should resolve identically to the correctly spelled word.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services for indiginous youth in the community."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    # ------------------------------------------------------------------
    # B4. Indigenous misspelling 'indigenious' → North American Indigenous
    # ------------------------------------------------------------------
    def test_indigenous_misspelling_indigenious_classifies(self):
        e1, e2, e3, flag = classify_row(
            row(desc="Support for indigenious elders and families."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    # ------------------------------------------------------------------
    # B5. Francophone context always emits accommodation note (P2-1 decoupled)
    # ------------------------------------------------------------------
    def test_francophone_context_always_emits_note(self):
        """
        Even when no French ethnic candidate is present to drop,
        a francophone-context match should emit the accommodation note.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services for francophone women in the Edmonton region."),
            TAXONOMY_B2,
        )
        self.assertIn("language accommodation", flag)

    # ------------------------------------------------------------------
    # B6. 'non-profit Indigenous' — non- prefix should NOT negate 'Indigenous'
    # ------------------------------------------------------------------
    def test_non_profit_indigenous_not_negated(self):
        """
        The bad pattern r"\\bnon[- ]?$" was removed from NEGATION_PHRASES.
        'non-profit Indigenous organization' must NOT negate the Indigenous signal.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="A non-profit Indigenous organization serving urban youth."),
            TAXONOMY_B2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    # ------------------------------------------------------------------
    # B7. Eritrean Cultural Association → review flag (Case 13)
    # ------------------------------------------------------------------
    def test_eritrean_cultural_association_flagged(self):
        """
        'eritrean' is not in taxonomy or COUNTRY_REGION_MAP, and 'eritrean'
        is not in NON_ETHNIC_LEADING_WORDS — Case 13 should flag it for review.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Eritrean Cultural Association"),
            TAXONOMY_B2,
        )
        self.assertIn("Potential ethnocultural organization name", flag)

    # ------------------------------------------------------------------
    # B8. Soccer Association — NOT flagged by Case 13 (looks_like_demonym gate)
    # ------------------------------------------------------------------
    def test_soccer_association_not_flagged(self):
        """
        'Soccer' is in NON_ETHNIC_LEADING_WORDS → looks_like_demonym returns False
        → Case 13 must NOT flag 'Soccer Association'.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Edmonton Soccer Association"),
            TAXONOMY_B2,
        )
        self.assertNotIn("Potential ethnocultural organization name", flag)

    # ------------------------------------------------------------------
    # B9. Import smoke test — constants export all expected names
    # ------------------------------------------------------------------
    def test_constants_exports_all_expected_names(self):
        """Verify that constants.py exports every name used by the pipeline."""
        import constants
        expected = [
            "MULTIPLE_ETHNIC", "OTHER_ETHNIC", "GENERAL_POP",
            "BIPOC_KEYWORDS", "AMBIGUOUS_EQUITY_WORDS", "BROAD_IDENTITY_KEYWORDS",
            "ALWAYS_MULTIPLE_COMPOUNDS", "ORG_NAME_ETHNICITY_MAP",
            "PATTERN_RULES", "COUNTRY_REGION_MAP",
            "EXPANSION_PHRASES", "HISTORICAL_PHRASES", "NEGATION_PHRASES",
            "ASPIRATIONAL_PHRASES", "EXAMPLE_PHRASES", "EXPERT_ROLE_PHRASES",
            "SERVING_CONTEXT_WORDS", "IDENTITY_PHRASE_REWRITES",
            "DIRECTIONAL_AFRICAN_PREFIXES", "CASE_13_PATTERNS",
            "DEMONYM_SUFFIXES", "NON_ETHNIC_LEADING_WORDS",
            "LANGUAGE_ACCOMMODATION_PATTERNS", "FRENCH_ETHNIC_KEEP_PATTERNS",
        ]
        for name in expected:
            self.assertTrue(hasattr(constants, name), f"constants.py missing: {name}")


# ---------------------------------------------------------------------------
# Name/body split (Phase 1, Chunk B) — Plan.md D1: a signal that lives only
# in the Funding Request Name must not classify on its own.
# ---------------------------------------------------------------------------

class TestNameBodySplit(unittest.TestCase):

    def test_council_body_black_wins_over_name_african(self):
        """
        Body says 'Black Edmontonians'/'Black professionals'; name says
        'African Canadians'. The body signal wins outright — the name is
        not even consulted once the body has a candidate.
        """
        e1, e2, e3, flag = classify_row(
            row(
                name="Council for the Advancement of African Canadians",
                desc="a health program for Black Edmontonians led by Black professionals",
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "Other Ethnic and Cultural Origins")
        self.assertEqual(e2, "Black, not otherwise specified")

    def test_name_only_ethnic_signal_degrades_to_general(self):
        """'Black Canadian Women in Action' with a truly neutral body (zero
        Black mentions anywhere, unlike real gold row 54525 which has a
        weak historical/self-reference mention -- see
        TestGenderSexualClassifier.test_org_name_echo_with_expansion_disclaimer_stays_general)
        is a silent body. Plan.md Chunk G1 step 5's generalizable
        silent-body name rule classifies from the name instead of the old
        flat General default -- always flagged."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Black Canadian Women in Action",
                desc="Funding will cover the Executive Director's salary and benefits.",
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "Other Ethnic and Cultural Origins")
        self.assertEqual(e2, "Black, not otherwise specified")
        self.assertIn("silent body", flag)

    def test_org_echo_ethnic_body_classifies_from_org_name(self):
        """G5: an org-name echo is the body's ONLY ethnic mention ("The Somali
        Canadian Society is replacing its sound system") — a weak self-
        reference, not a served signal. The body is administratively silent,
        so classify from the org name + flag instead of the old flat General.
        Mirrors real gold rows Jewish Family Services 50644 -> Jewish and
        Ukrainian Shumka 54507 -> Ukrainian."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Somali Canadian Society",
                desc=("The Somali Canadian Society is replacing the sound "
                      "system in its community hall."),
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e3, "Somali")
        self.assertIn("silent body", flag)

    def test_known_org_in_name_still_classifies(self):
        """Niginan Housing Ventures (curated known-org map) classifies from
        the name alone even with an empty body — the D1 exception."""
        e1, e2, e3, flag = classify_row(
            row(name="Niginan Housing Ventures"),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_body_signal_still_classifies(self):
        """A real signal in the body classifies normally regardless of the
        name (regression guard for the split itself)."""
        e1, e2, e3, flag = classify_row(
            row(desc="programming for Somali youth"),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e3, "Somali")


# ---------------------------------------------------------------------------
# Phase 2 — Evidence-role tiering (Plan.md Fix 1 Phase 2), tied to real gold
# rows: Alberta Ballet 51597 (org_name descriptor demoted, African survives
# as served) and Digestive Health/CDHF (provider-only mention demotes to
# General + transparency note).
# ---------------------------------------------------------------------------

class TestEvidenceRoleTiering(unittest.TestCase):

    def test_alberta_ballet_black_descriptor_demoted_african_survives(self):
        """
        Real gold row (Alberta Ballet 51597): 'Black' only appears as a
        proper-noun descriptor ('the first Black classical ballet company')
        — org_name role, demoted. 'African' appears as the served population
        ('dance program for youth of African descent') — served, survives.
        Resolves to African Origins alone, not Multiple.
        """
        e1, e2, e3, flag = classify_row(
            row(
                name="Alberta Ballet Company",
                desc=(
                    "Alberta Ballet, in partnership with Africa Centre, is expanding its "
                    "outreach dance program for youth of African descent in Edmonton. The "
                    "program culminated in a masterclass with the Dance Theatre of Harlem, "
                    "the first Black classical ballet company."
                ),
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "African Origins")
        self.assertNotEqual(e1, MULTIPLE_ETHNIC)

    def test_provider_only_mention_demotes_to_general_with_note(self):
        """
        A group named only via a provider/professional-title construction
        ('Sharon Swampy, Indigenous Nutritionist') is not the served
        population — General + a transparency note naming the group and
        its role (partial Fix 7), not a classification.
        """
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Sharon Swampy, Indigenous Nutritionist, will lead the workshop "
                "on digestive health for the general public."
            )),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("provider context only", flag)

    def test_council_51599_provider_mention_does_not_demote_when_served_present(self):
        """
        Counter-example (guardrail): when the SAME group has both a served
        mention and a provider mention ('program for Black Edmontonians ...
        delivered by Black professionals'), the served mention rescues the
        group — provider mentions only demote a group that has NO served
        mention anywhere."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Council for the Advancement of African Canadians",
                desc=(
                    "a health program for Black Edmontonians, delivered by "
                    "Black professionals"
                ),
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "Other Ethnic and Cultural Origins")
        self.assertEqual(e2, "Black, not otherwise specified")


# ---------------------------------------------------------------------------
# Gender + Sexual Identity classifier tests
# Tests item 1–4 from the audit-driven improvement spec.
# ---------------------------------------------------------------------------

from Gender_SexID import (
    classify_gender, classify_sexual,
    GENDER_GENERAL_POP, GENDER_MULTIPLE, GENDER_OTHER,
    GENDER_WOMEN_GIRLS, GENDER_MEN_BOYS,
    SEXUAL_2SLGBTQIA, SEXUAL_GENERAL_POP,
)
from gender_constants import FLAG_ORG_NAME, SFLAG_GENDER_TERM


class TestGenderSexualClassifier(unittest.TestCase):
    """Tests for all five audit-driven fixes to the gender/sexual classifier."""

    # ------------------------------------------------------------------
    # Item 1 — LGBTQ acronym → Multiple gender identities
    # ------------------------------------------------------------------
    def test_lgbtq_alone_produces_multiple(self):
        """Bare 'lgbtq' → Multiple (not Other); flag names acronym source."""
        label, flag = classify_gender(row(desc="Services for the lgbtq community."))
        self.assertEqual(label, GENDER_MULTIPLE)
        self.assertIn("2SLGBTQIA+", flag)

    def test_lgbtqplus_produces_multiple(self):
        """'lgbtq+' → Multiple (+ is stripped by normalize_text)."""
        label, flag = classify_gender(row(desc="Supporting lgbtq+ youth."))
        self.assertEqual(label, GENDER_MULTIPLE)

    def test_lgbtqia_produces_multiple(self):
        """'lgbtqia' variant → Multiple."""
        label, flag = classify_gender(row(desc="Programs for the lgbtqia community."))
        self.assertEqual(label, GENDER_MULTIPLE)

    def test_2slgbtqia_produces_multiple_with_two_spirit_flag(self):
        """'2SLGBTQIA+' → Multiple; Two-Spirit cross-check flag present."""
        label, flag = classify_gender(row(desc="Serving 2SLGBTQIA+ individuals."))
        self.assertEqual(label, GENDER_MULTIPLE)
        self.assertIn("Two-Spirit", flag)

    def test_lone_queer_produces_other_not_multiple(self):
        """A single 'queer' (no umbrella acronym) → Other, not Multiple."""
        label, flag = classify_gender(row(desc="A queer youth program."))
        self.assertEqual(label, GENDER_OTHER)
        self.assertNotEqual(label, GENDER_MULTIPLE)

    def test_two_concrete_keys_produces_multiple_with_no_flag(self):
        """Plan.md Chunk G10 item 1: 2+ concrete, non-diverse keys (men/boys
        + women/girls here) → Multiple gender identities with NO primary
        flag -- the generic "Multiple: <identities>" text was dropped as
        noise (unlike the lgbtq_umbrella and gender_diverse branches above,
        which keep their flag)."""
        label, flag = classify_gender(row(desc="Programming for both men and women in the community."))
        self.assertEqual(label, GENDER_MULTIPLE)
        self.assertEqual(flag, "")

    # ------------------------------------------------------------------
    # Item 2 — Org / proper-name context: keep classification + add flag
    # ------------------------------------------------------------------
    def test_boys_girls_club_classified_and_flagged(self):
        """'Boys & Girls Club' with no body text is a silent body. Plan.md
        Chunk G1 step 5's name rule finds BOTH women/men terms in the name
        ("boys" and "girls") -> General Population (the "both present"
        case), flagged for verification -- not FLAG_ORG_NAME (that fires
        only on a body-text org-name construct, and there's no body here)."""
        label, flag = classify_gender(row(name="Boys and Girls Club of Edmonton"))
        self.assertEqual(label, GENDER_GENERAL_POP)
        self.assertIn("silent body", flag)

    def test_institute_for_women_classified_and_flagged(self):
        """'Institute for Women' → Women and/or girls + FLAG_ORG_NAME."""
        label, flag = classify_gender(row(desc="The institute for women provides programming."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn(FLAG_ORG_NAME, flag)

    def test_wardrobe_for_women_name_only_degrades_to_general(self):
        """'Wardrobe for Women Association' with a neutral body (ED salary,
        zero gender-term mentions) is a silent body. Plan.md Chunk G1 step 5
        classifies from the name's "Women" term instead of the old flat
        General default -- Women and/or girls, flagged for verification."""
        label, flag = classify_gender(row(
            name="Suit Yourself - Wardrobe for Women Association",
            desc="Funding will cover the Executive Director's salary and benefits.",
        ))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn("silent body", flag)

    def test_boys_girls_clubs_big_brothers_big_sisters_name_only(self):
        """'Boys & Girls Clubs Big Brothers Big Sisters' with an empty body
        is a silent body; the name carries BOTH women/men terms (girls/
        sisters AND boys/brothers) -> General Population (Plan.md Chunk G1
        step 5's "both present" case), flagged for verification."""
        label, flag = classify_gender(row(name="Boys & Girls Clubs Big Brothers Big Sisters"))
        self.assertEqual(label, GENDER_GENERAL_POP)
        self.assertIn("silent body", flag)

    def test_org_name_echo_with_expansion_disclaimer_stays_general(self):
        """
        Real gold row (Black Canadian Women in Action 54525): the org
        restates its own name AND explicitly disclaims it as the CURRENT
        served population ("beyond its original focus on Black communities").
        The G5 disclaimer guard (IDENTITY_EXPANSION_DISCLAIMER_PATTERNS) keeps
        this General — the org-name signal is NOT borrowed when the body says
        the org has moved past that identity.
        """
        label, flag = classify_gender(row(
            name="Black Canadian Women in Action",
            desc=(
                "Black Canadian Women in Action (BCW) is undertaking a major "
                "capacity-building initiative as families from increasingly "
                "diverse backgrounds turn to BCW for support beyond its "
                "original focus on Black communities."
            ),
        ))
        self.assertEqual(label, GENDER_GENERAL_POP)

    def test_org_echo_only_body_classifies_from_org_name(self):
        """G5 org-name ladder: an org-name echo with NO other ethnic or
        gender/sex signal in the body classifies from the org-name signal +
        flag (real gold row Alberta Immigrant Women & Children Centre 54640 —
        an admin/autism body serving 'newcomer families', which is not itself
        a gender signal, so the org's 'Women' name wins). Stakeholder-
        confirmed 2026-07-13; gold reconciled to Women and/or girls."""
        label, flag = classify_gender(row(
            name="Alberta Immigrant Women & Children Centre",
            summary=(
                "The Alberta Immigrant Women & Children Centre (AIWCC) seeks "
                "renewed funding to sustain the Client Services position, "
                "helping parents connect with autism services."
            ),
        ))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn("organization name", flag)

    def test_org_echo_both_genders_in_name_stays_general(self):
        """Real gold row (Boys & Girls Clubs Big Brothers Big Sisters 50610):
        the body echoes an abbreviated form of the org's own name. The org-name
        ladder fires, but the name carries BOTH women (girls/sisters) and men
        (boys/brothers) terms → General (all-youth org), now with the silent-
        body name-rule flag rather than the self-reference note."""
        label, flag = classify_gender(row(
            name="Boys & Girls Clubs Big Brothers Big Sisters of Edmonton",
            desc=(
                "We are asking the Edmonton Community Foundation to support "
                "BGC Big Brothers Big Sisters to assist with upgrading "
                "technology across three organizational domains."
            ),
        ))
        self.assertEqual(label, GENDER_GENERAL_POP)

    def test_org_echo_admin_body_classifies_women_from_name(self):
        """G5 (real gold row Women Building Futures 54513): a pure-admin body
        that only echoes the org's own name ("Women Building Futures must
        replace its servers") is administratively silent — classify Women from
        the name + flag, not the old General."""
        label, flag = classify_gender(row(
            name="Women Building Futures Society",
            desc=(
                "Women Building Futures must replace the existing servers to "
                "ensure program data remains secure."
            ),
        ))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn("organization name", flag)

    def test_org_flag_not_fired_for_plain_gender_description(self):
        """A plain description like 'serving women in Edmonton' has no org noun
        — FLAG_ORG_NAME must NOT fire."""
        label, flag = classify_gender(row(desc="Serving women in Edmonton."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertNotIn(FLAG_ORG_NAME, flag)

    # ------------------------------------------------------------------
    # Item 3 — Gender-diverse term → Sexual: SFLAG_GENDER_TERM now scoped to
    # the ambiguous "gender-diverse" umbrella term only (Plan.md Chunk G10
    # item 2) — trans/non-binary/two-spirit/etc. unambiguously belong under
    # 2SLGBTQIA+ already, so they no longer carry the flag.
    # ------------------------------------------------------------------
    def test_trans_youth_produces_sexual_2slgbtqia_no_gender_flag(self):
        """'trans youth' → Sexual 2SLGBTQIA+; SFLAG_GENDER_TERM no longer
        fires for "trans" specifically (only for the "gender-diverse" key)."""
        label, flag = classify_sexual(row(desc="Program serving trans youth."))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertNotIn(SFLAG_GENDER_TERM, flag)

    def test_trans_plus_gay_no_gender_flag(self):
        """'trans and gay' → 2SLGBTQIA+; SFLAG_GENDER_TERM absent (neither
        "trans" nor "gay" is the ambiguous "gender-diverse" umbrella term)."""
        label, flag = classify_sexual(row(desc="Resources for trans and gay individuals."))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertNotIn(SFLAG_GENDER_TERM, flag)

    def test_gender_diverse_term_still_flags_gender_term(self):
        """'gender-diverse' specifically → 2SLGBTQIA+ with SFLAG_GENDER_TERM
        still present (Plan.md Chunk G10 item 2 kept this one case — the
        umbrella term itself is genuinely ambiguous)."""
        label, flag = classify_sexual(row(desc="Program serving gender-diverse youth and gay adults."))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertIn(SFLAG_GENDER_TERM, flag)

    def test_lesbian_only_no_gender_flag(self):
        """Pure orientation term ('lesbian') → 2SLGBTQIA+; SFLAG_GENDER_TERM absent."""
        label, flag = classify_sexual(row(desc="A program for lesbian women."))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertNotIn(SFLAG_GENDER_TERM, flag)

    # ------------------------------------------------------------------
    # Item 4 — Vocabulary expansion (familial terms)
    # ------------------------------------------------------------------
    def test_single_mothers_classified_as_women_girls(self):
        """'single mothers' → Women and/or girls."""
        label, flag = classify_gender(row(desc="Supporting single mothers in our community."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)

    def test_fathers_group_classified_as_men_boys(self):
        """'fathers group' → Men and/or boys."""
        label, flag = classify_gender(row(desc="A fathers group for new parents."))
        self.assertEqual(label, GENDER_MEN_BOYS)

    def test_grandmothers_classified_as_women_girls(self):
        """'grandmothers' → Women and/or girls."""
        label, flag = classify_gender(row(desc="Programming for Indigenous grandmothers."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)

    def test_grandfathers_classified_as_men_boys(self):
        """'grandfathers' → Men and/or boys."""
        label, flag = classify_gender(row(desc="Cultural program for grandfathers and elders."))
        self.assertEqual(label, GENDER_MEN_BOYS)

    def test_maternal_classified_as_women_girls(self):
        """'maternal' → Women and/or girls."""
        label, flag = classify_gender(row(desc="Addressing maternal health outcomes."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)

    def test_paternal_classified_as_men_boys(self):
        """'paternal' → Men and/or boys."""
        label, flag = classify_gender(row(desc="Supporting paternal mental health."))
        self.assertEqual(label, GENDER_MEN_BOYS)

    # ------------------------------------------------------------------
    # Item 4 — Ambiguous coded terms: classification unaffected, flag
    # removed entirely (Plan.md Chunk G10 item 3)
    # ------------------------------------------------------------------
    def test_femme_alone_classifies_no_ambiguous_flag(self):
        """
        'femme-identified' alone → Women and/or girls (Fix 8: "femme" is
        French for "woman", a real classifying signal); FLAG_AMBIGUOUS_TERM
        no longer fires (removed entirely per G10 item 3).
        """
        label, flag = classify_gender(row(desc="Serving femme-identified individuals."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertNotIn("Ambiguous coded", flag)

    def test_butch_alone_does_not_classify(self):
        """'butch' alone → General Population, no ambiguous-term flag."""
        label, flag = classify_gender(row(desc="Programming for butch community members."))
        self.assertEqual(label, GENDER_GENERAL_POP)
        self.assertNotIn("Ambiguous coded", flag)

    def test_femme_with_clear_signal_keeps_classification_no_flag(self):
        """'femme women' — clear 'women' signal classifies; no ambiguous-term flag."""
        label, flag = classify_gender(row(desc="Support for femme women in the community."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertNotIn("Ambiguous coded", flag)

    # ------------------------------------------------------------------
    # Fix 8 — French gender terms
    # ------------------------------------------------------------------
    def test_french_femmes_plural_classifies_as_women_girls(self):
        """'femmes' (French plural, no coded-slang ambiguity in this form)
        → Women and/or girls."""
        label, flag = classify_gender(row(desc="Un programme pour les femmes immigrantes."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)

    def test_french_hommes_classifies_as_men_boys(self):
        """'hommes' (French for men) → Men and/or boys."""
        label, flag = classify_gender(row(desc="Un programme de soutien pour les hommes."))
        self.assertEqual(label, GENDER_MEN_BOYS)

    def test_association_femme_moderne_name_only_degrades_to_general(self):
        """'Association Femme Moderne' with a neutral body (zero gender-term
        mentions) is a silent body. Plan.md Chunk G1 step 5 classifies from
        the name's "Femme" term (French for woman) -> Women and/or girls,
        flagged for verification -- superseding the old Fix 8 flat-General
        default for this exact silent-body shape."""
        label, flag = classify_gender(row(
            name="Association Femme Moderne",
            desc="Funding will cover office rent and administrative costs.",
        ))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn("silent body", flag)

    # ------------------------------------------------------------------
    # Regression — negation still suppresses
    # ------------------------------------------------------------------
    def test_negation_on_women_suppresses_and_flags(self):
        """'not serving women' — negation detected; classification may still proceed
        (negation is annotation-only) but FLAG_NEGATION must appear."""
        label, flag = classify_gender(row(desc="This program is not serving women exclusively."))
        self.assertIn("negation word", flag)

    def test_empty_row_returns_general_pop(self):
        """All columns empty → General Population, no crash."""
        g_label, g_flag = classify_gender(row())
        s_label, s_flag = classify_sexual(row())
        self.assertEqual(g_label, GENDER_GENERAL_POP)
        self.assertEqual(s_label, SEXUAL_GENERAL_POP)

    # ------------------------------------------------------------------
    # Fix 7 — transparency note for example-suppressed sexual-identity signal
    # ------------------------------------------------------------------
    def test_sexual_example_suppression_leaves_transparency_note(self):
        """'... groups such as 2SLGBTQIA+ ...' is a real gold pattern (Autism
        54463, CMHA 54531): the signal is correctly suppressed as an
        example/illustrative mention, but General is annotated with a note
        naming what was dropped instead of vanishing with no trace."""
        label, flag = classify_sexual(row(
            desc="We support equity-deserving groups such as 2SLGBTQIA+ individuals and newcomers."
        ))
        self.assertEqual(label, SEXUAL_GENERAL_POP)
        self.assertIn("2SLGBTQIA+ mentioned in example/illustrative context", flag)

    # ------------------------------------------------------------------
    # Fix 2a — "gender-diverse" is a distinct concept, not a single identity
    # ------------------------------------------------------------------
    def test_gender_diverse_alone_produces_gender_multiple(self):
        """'gender-diverse' alone → Multiple gender identities (Plan.md Fix 2a)."""
        label, flag = classify_gender(row(desc="Programming for gender-diverse youth."))
        self.assertEqual(label, GENDER_MULTIPLE)
        self.assertIn("gender-diverse", flag)

    def test_gender_diverse_no_hyphen_produces_gender_multiple(self):
        """'gender diverse' (no hyphen, normalize_text strips punctuation
        anyway) → Multiple gender identities."""
        label, flag = classify_gender(row(desc="Support for gender diverse individuals."))
        self.assertEqual(label, GENDER_MULTIPLE)

    def test_gender_diverse_produces_sexual_2slgbtqia(self):
        """'gender-diverse' also signals 2SLGBTQIA+ on the sexual axis, via
        SEXUAL_GENDER_DIVERSE_KEYS (Plan.md Fix 2a)."""
        label, flag = classify_sexual(row(desc="Programming for gender-diverse youth."))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertIn(SFLAG_GENDER_TERM, flag)

    # ------------------------------------------------------------------
    # Fix 2b — "Womens'"/"Mens'" plural-possessive tokenization
    # ------------------------------------------------------------------
    def test_womens_plural_possessive_classified(self):
        """normalize_text strips the trailing apostrophe in "Womens'" down to
        one token "womens" (no space) — \\bwomen\\b alone would miss it;
        \\bwomens?\\b catches it."""
        label, flag = classify_gender(row(desc="Serving the Womens' outreach group."))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)

    def test_mens_plural_possessive_classified(self):
        """Same plural-possessive tokenization fix, men's side."""
        label, flag = classify_gender(row(desc="Serving the Mens' outreach group."))
        self.assertEqual(label, GENDER_MEN_BOYS)


# ---------------------------------------------------------------------------
# ML AUGMENTATION LAYER — Phase B: evidence-role NLI arbiter
# (Plan.md "ML AUGMENTATION LAYER" section). The arbiter is gated behind
# USE_ML_ROLE_ARBITER (off by default) and calls the real vendored NLI
# model when on — these tests mock ml_arbiter.nli_role so the plumbing
# (override/no-override, note text, margin gating) is verified
# deterministically without depending on the model's exact probabilistic
# output or paying its load time in every test run.
# ---------------------------------------------------------------------------

class TestMLRoleArbiter(unittest.TestCase):

    def setUp(self):
        import classify_pipeline
        self.classify_pipeline = classify_pipeline
        self._orig_flag = classify_pipeline.USE_ML_ROLE_ARBITER

    def tearDown(self):
        self.classify_pipeline.USE_ML_ROLE_ARBITER = self._orig_flag

    def _candidate(self, role="served", span="Somali", context="ctx"):
        return {
            "level1": "African Origins", "level2": "Southern and East African Origins",
            "level3": "Somali", "depth": 3, "source": "taxonomy",
            "role": role, "span": span, "context": context,
        }

    def test_flag_off_is_a_no_op(self):
        """Default state: apply_ml_role_arbiter must not touch candidates
        when the flag is off — zero behavior change to the shipping
        rule-only path."""
        self.classify_pipeline.USE_ML_ROLE_ARBITER = False
        candidates = [self._candidate()]
        result = self.classify_pipeline.apply_ml_role_arbiter(candidates)
        self.assertEqual(result, candidates)

    def test_flag_on_never_changes_role_at_high_margin(self):
        """Even at high confidence, the arbiter is advisory-only: role and
        classification are never mutated -- only ml_role_note is attached,
        worded as a high-confidence verify note."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": 2.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("Somali", result[0]["ml_role_note"])
        self.assertIn("high confidence", result[0]["ml_role_note"])
        self.assertNotIn("Note (low priority)", result[0]["ml_role_note"])

    def test_flag_on_low_priority_note_in_ambiguity_moat(self):
        """A margin inside the 0.5-1.5 ambiguity moat attaches a low-priority
        verify note -- still never changes role."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": 1.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("Note (low priority)", result[0]["ml_role_note"])

    def test_flag_on_keeps_served_when_margin_not_cleared(self):
        """A weak-role verdict that doesn't clear ML_ROLE_NOTE_MARGIN
        leaves the candidate untouched entirely -- no note attached."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 1.0, "org_name": 1.2, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertNotIn("ml_role_note", result[0])

    def test_flag_on_topic_hypothesis_produces_note_not_change(self):
        """The new 'topic' hypothesis behaves like any other weak role:
        advisory note only, never a role change."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": -5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": 2.0,
                        "aspirational": -5.0, "best_role": "topic"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("topic", result[0]["ml_role_note"])

    def test_flag_on_aspirational_hypothesis_produces_note_not_change(self):
        """The new 'aspirational' hypothesis behaves like any other weak
        role: advisory note only, never a role change."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": -5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": 2.0, "best_role": "aspirational"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("aspirational", result[0]["ml_role_note"])

    def test_flag_on_allyship_hypothesis_produces_note_not_change(self):
        """The new 'allyship' hypothesis (partnership/solidarity framing,
        e.g. 'an ally to Indigenous people') behaves like any other weak
        role: advisory note only, never a role change -- even though the
        regex frame that covers the same case collapses it into 'topic'."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": -5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "allyship": 2.0, "best_role": "allyship"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("allyship", result[0]["ml_role_note"])

    def test_flag_on_negated_hypothesis_now_produces_note(self):
        """Regression test: 'negated' used to be silently discarded
        alongside 'served' (a no-op with zero output regardless of
        confidence). Under the flag-only redesign there's no reason to keep
        suppressing it -- a confident negated verdict must now produce a
        note, worded via the 'may be explicitly excluded' clause rather
        than the generic 'reads as <role>' phrasing."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": -5.0, "provider": -5.0,
                        "example": -5.0, "negated": 2.0, "topic": -5.0,
                        "aspirational": -5.0, "allyship": -5.0, "best_role": "negated"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate()])
        self.assertEqual(result[0]["role"], "served")
        self.assertIn("ml_role_note", result[0])
        self.assertIn("explicitly excluded", result[0]["ml_role_note"])

    def test_flag_on_never_promotes_weak_to_served(self):
        """A candidate the regex already tagged weak (e.g. 'example') is
        left alone — the arbiter only demotes 'served', never promotes."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 5.0, "org_name": -5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "best_role": "served"}
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            result = self.classify_pipeline.apply_ml_role_arbiter([self._candidate(role="example")])
        self.assertEqual(result[0]["role"], "example")

    def test_candidate_without_span_passes_through(self):
        """org_lookup-style candidates (no span/context captured) skip the
        arbiter entirely rather than erroring on an empty premise."""
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        candidates = [self._candidate(span="", context="")]
        result = self.classify_pipeline.apply_ml_role_arbiter(candidates)
        self.assertEqual(result[0]["role"], "served")
        self.assertNotIn("ml_role_note", result[0])

    def test_env_var_sets_flag_at_import_time(self):
        """USE_ML_ROLE_ARBITER reads os.environ at import time so
        audit_score.py can A/B test the arbiter with no code change."""
        self.assertFalse(
            self.classify_pipeline.USE_ML_ROLE_ARBITER,
            "test process must run with USE_ML_ROLE_ARBITER unset for this "
            "assertion to be meaningful",
        )

    def test_stakeholder_reviewed_row_skips_arbiter_entirely(self):
        """classify_row() must never invoke the ML arbiter on a row already
        marked stakeholder-reviewed (FR testing.xlsx column AN non-blank) --
        no ml_role_note should reach the flag output regardless of margin."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": 5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        reviewed_row = row(desc="A program serving the Somali community.")
        reviewed_row[STAKEHOLDER_REVIEWED_COL] = "Wrong Ethnic"
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            e1, e2, e3, flag = classify_row(reviewed_row, TAXONOMY)
        self.assertNotIn("ML role arbiter", flag)

    def test_unreviewed_row_still_reaches_arbiter(self):
        """Sanity check for the above: the same row WITHOUT a stakeholder
        review mark does reach the arbiter (control case)."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": 5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        plain_row = row(desc="A program serving the Somali community.")
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            e1, e2, e3, flag = classify_row(plain_row, TAXONOMY)
        self.assertIn("ML role arbiter", flag)

    def test_nan_stakeholder_column_still_reaches_arbiter(self):
        """Regression test: a pandas row's BLANK AN cell is a float NaN, not
        "" -- `row.get(col, "") or ""` is wrong (its default only applies
        when the key is absent, never when the value is NaN, and NaN is
        truthy in Python), so every real pandas-sourced row was silently
        treated as reviewed and the arbiter never ran on live data. A plain
        dict test with a missing/empty-string key can't catch this -- it
        must use an actual float NaN, as pd.read_excel produces."""
        import unittest.mock as mock
        self.classify_pipeline.USE_ML_ROLE_ARBITER = True
        fake_scores = {"served": 0.0, "org_name": 5.0, "provider": -5.0,
                        "example": -5.0, "negated": -5.0, "topic": -5.0,
                        "aspirational": -5.0, "best_role": "org_name"}
        nan_row = row(desc="A program serving the Somali community.")
        nan_row[STAKEHOLDER_REVIEWED_COL] = float("nan")
        with mock.patch("ml_arbiter.nli_role", return_value=fake_scores):
            e1, e2, e3, flag = classify_row(nan_row, TAXONOMY)
        self.assertIn("ML role arbiter", flag)



# ---------------------------------------------------------------------------
# Chunk G1 — Org-name handling (echo demotion + generalizable silent-body
# name rule). Tied to real gold rows: 54525 (Black Canadian Women in Action,
# ethnic + gender), 51622 (BCW/Haitian youth, gender cross-axis gate), the
# SCERDO/Somali silent-body rows, and the reviewer-verified "Correct Sex &
# Gender" column for the Edmonton Women's Shelter / Wardrobe for Women /
# Alberta Immigrant Women & Children Centre rows.
# ---------------------------------------------------------------------------

class TestG1SilentBodyNameRule(unittest.TestCase):
    """Ethnic axis — generalizable silent-body name rule (Plan.md step 5)."""

    def test_silent_body_umbrella_term_classifies_umbrella(self):
        """A truly silent body (no desc) with an umbrella ethnic term
        ('African') in the name classifies at the umbrella L1, flagged."""
        e1, e2, e3, flag = classify_row(
            row(name="African Heritage Foundation"),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "")
        self.assertIn("silent body", flag)

    def test_silent_body_two_distinct_groups_produces_multiple(self):
        """Two distinct L1 identity terms in a silent-body name -> Multiple."""
        e1, e2, e3, flag = classify_row(
            row(name="African and Caribbean Descendants Society"),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("silent body", flag)

    def test_silent_body_bipoc_name_produces_multiple(self):
        """A BIPOC-only silent-body name -> Multiple, same umbrella treatment
        as a body-text BIPOC mention."""
        e1, e2, e3, flag = classify_row(
            row(name="BIPOC Arts Collective"),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("silent body", flag)

    def test_silent_body_islamic_org_stays_general(self):
        """Exclusion (Plan.md step 5): religion-only silent-body name
        ('Islamic') stays General + a targeted note, not a guessed ethnicity."""
        e1, e2, e3, flag = classify_row(
            row(name="Islamic Relief Foundation"),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("not an ethnic signal", flag)

    def test_silent_body_francophone_org_stays_general(self):
        """Exclusion: language-only silent-body name ('Francophone') stays
        General + a targeted note."""
        e1, e2, e3, flag = classify_row(
            row(name="Francophone Community Centre"),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("not an ethnic signal", flag)


class TestG1EchoDemotionAndServedRescue(unittest.TestCase):
    """Ethnic axis — org-name echo demotion (steps 1/4) vs served-frame
    rescue (step 2). Regression guards for the real gold row 54525 shape
    (org self-intro + historical framing -> General) and the over-broad
    name-word-echo bug this work order caught and fixed (a body mention
    that merely shares a word with the org's name, but is a genuine served
    claim in ordinary prose, must NOT be demoted)."""

    def test_org_self_intro_plus_historical_focus_demotes_to_general(self):
        """Real gold row 54525 shape: the org restates its own name AND
        separately describes Black as its HISTORICAL focus ('beyond its
        original focus on') with no served frame anywhere -> General."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Black Advocates in Action",
                desc=(
                    "Black Advocates in Action (BAA) is undertaking a "
                    "rebranding initiative. As the organization grows beyond "
                    "its original focus on Black communities, it now serves "
                    "diverse communities across the city."
                ),
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("not classified as served population", flag)

    def test_served_claim_sharing_a_word_with_org_name_is_not_demoted(self):
        """Regression guard: ordinary prose describing the served population
        ('support ... Black mothers') must classify normally even though
        the org's own name ('Black Mothers Support Network') shares the
        word 'Black' -- there is no historical/expansion framing here, so
        the echo-demotion upgrade (step 4) must NOT fire."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Black Mothers Support Network",
                desc=(
                    "Our volunteer-run circles support immigrant and Black "
                    "mothers facing isolation and financial strain."
                ),
            ),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, "Other Ethnic and Cultural Origins")
        self.assertEqual(e2, "Black, not otherwise specified")

    def test_ethnic_org_name_serving_language_rescues_despite_name_overlap(self):
        """Served-frame rescue (step 2): an explicit 'serving X' lead-in
        keeps the group served even though the org's own name also carries
        that word -- 'Somali Canadian Cultural Society ... serving the
        Somali community' must stay Somali, not demote to an org-name echo."""
        e1, e2, e3, flag = classify_row(
            row(
                name="Somali Canadian Cultural Society",
                desc="Historically serving the Somali community, this program continues today.",
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e3, "Somali")


class TestG1GenderSexualSilentBodyAndCrossAxisGate(unittest.TestCase):
    """Gender/Sexual axes — generalizable silent-body name rule (Plan.md
    step 5) plus the cross-axis 'truly administrative' gate (Plan.md FIX,
    validated against the reviewer 'Correct Sex & Gender' column for real
    gold rows 51622/54130/54496)."""

    def test_silent_body_men_org_classifies_men_boys(self):
        """A truly silent body with a men/boys term in the name (Plan.md
        step 5's GENDER_SILENT_NAME_MEN_PATTERN) classifies Men and/or boys."""
        label, flag = classify_gender(row(name="Fathers Support Circle"))
        self.assertEqual(label, GENDER_MEN_BOYS)
        self.assertIn("silent body", flag)

    def test_silent_body_pride_org_classifies_2slgbtqia(self):
        """A truly silent body with a sexual-identity term in the name
        (Plan.md step 5's SEXUAL_SILENT_NAME_PATTERN) classifies 2SLGBTQIA+."""
        label, flag = classify_sexual(row(name="Pride Alliance Network"))
        self.assertEqual(label, SEXUAL_2SLGBTQIA)
        self.assertIn("silent body", flag)

    def test_gender_stays_general_when_body_serves_nongendered_population(self):
        """Real gold row 51622 shape (reviewer 'Correct Sex & Gender' = NO,
        should be General): the body genuinely serves a real population
        ('Haitian youth') that simply isn't gendered -- the cross-axis gate
        must block the gender name rule from borrowing 'Women' off the org
        name, leaving plain General + the old org-name-context flag."""
        label, flag = classify_gender(row(
            name="Haitian Women's Network",
            desc="Our program serves Haitian youth with after-school tutoring.",
        ))
        self.assertEqual(label, GENDER_GENERAL_POP)
        self.assertIn(FLAG_ORG_NAME, flag)

    def test_gender_classifies_from_name_when_body_truly_administrative(self):
        """Real gold row shape (Edmonton Women's Shelter bathroom-vanity
        replacement / Wardrobe for Women ED-salary continuity -- reviewer
        'Correct Sex & Gender' = YES): a genuinely administrative body (no
        population named on any axis) lets the org name drive the gender
        classification."""
        label, flag = classify_gender(row(
            name="Edmonton Women's Shelter Ltd.",
            desc="This project will replace worn-out bathroom vanities to meet health inspection standards.",
        ))
        self.assertEqual(label, GENDER_WOMEN_GIRLS)
        self.assertIn("silent body", flag)


# ---------------------------------------------------------------------------
# Chunk G2 — Gender incidental family-context guard (row 54093)
# ---------------------------------------------------------------------------

TAXONOMY_G2 = TAXONOMY + [
    {
        "keyword": "ukrainian",
        "level1": "European Origins",
        "level2": "Eastern European Origins",
        "level3": "Ukrainian",
        "depth": 3,
    },
]


class TestG2GenderIncidentalFamilyContextGuard(unittest.TestCase):
    """Plan.md Chunk G2: a bare relational-male noun (fathers/brothers/sons/
    dads) that only mentions an absent/left-behind family member is NOT a
    served-gender signal -- mirrors the served-vs-mentioned weak-role
    pattern already used for org-name echoes."""

    def test_row_54093_fathers_left_behind_demotes_to_general_ethnic_unchanged(self):
        """Real gold row shape (54093): 'their fathers... remain in Ukraine'
        is an incidental mention of an absent relative, not the served
        population (Ukrainian youth) -- gender degrades to General
        Population + a transparency note. Ethnic classification (European
        Origins / Eastern European Origins -- matches the real production
        row's evidence, where the co-occurring "Eastern European" phrase
        keeps resolution at L2) is driven by the separate ethnic pipeline
        and must stay unaffected by the gender guard."""
        r = row(
            desc=(
                "We are planning a Christmas celebration for 110 Ukrainian and "
                "Eastern European youth who have arrived in Edmonton since 2022 "
                "after fleeing the war in Ukraine. Many of these youth came with "
                "only one parent while their fathers, friends, and extended "
                "family remain in Ukraine. They are experiencing stress, "
                "language barriers, and financial hardship."
            ),
        )
        g_label, g_flag = classify_gender(r)
        self.assertEqual(g_label, GENDER_GENERAL_POP)
        self.assertIn("incidental family context", g_flag)

        e1, e2, e3, _ = classify_row(r, TAXONOMY_G2)
        self.assertEqual(e1, "European Origins")
        self.assertEqual(e2, "Eastern European Origins")

    def test_genuine_served_men_and_boys_body_still_classifies_men_boys(self):
        """Guard must not be over-broad: a body that genuinely serves men
        and boys (no left-behind/family-context framing) still classifies
        Men and/or boys."""
        label, flag = classify_gender(row(
            desc="This program provides after-school recreational activities for young men and boys in the community."
        ))
        self.assertEqual(label, GENDER_MEN_BOYS)

    def test_fathers_separated_from_children_stays_general(self):
        """A second left-behind phrasing ('separated from their fathers who
        stayed behind') -- still an incidental mention, not served."""
        label, flag = classify_gender(row(
            desc=(
                "These newcomer youth were separated from their fathers, who "
                "stayed behind during the evacuation. The program supports the "
                "youth with counselling and peer connection."
            )
        ))
        self.assertEqual(label, GENDER_GENERAL_POP)
        self.assertIn("incidental family context", flag)

    def test_fathers_group_unaffected_by_guard(self):
        """Regression guard: a direct 'fathers group' mention (no
        left-behind framing) is unaffected by the G2 guard -- still Men
        and/or boys (mirrors the existing test_fathers_group_classified_as_men_boys)."""
        label, flag = classify_gender(row(desc="A fathers group for new parents."))
        self.assertEqual(label, GENDER_MEN_BOYS)


class TestG3IndigenousPatternPathRoleTiering(unittest.TestCase):
    """Plan.md Chunk G3: Indigenous PATTERN candidates ('indigenous'/
    'aboriginal'/etc, matched via PATTERN_RULES) already flowed through
    infer_role, but a curriculum/topic framing ('Indigenous perspectives'
    as course content) and a consulted-party framing ('Indigenous
    knowledge holders' consulted alongside other experts) weren't covered
    by the existing provider/org_name weak-role frames -- both wrongly
    classified as served. A new weak 'topic' role demotes them when no
    served-Indigenous frame rescues the row elsewhere; served mentions,
    residential-school/Truth-and-Reconciliation/ceremony context, and
    served-population lists are preserved. Verified over all 448 live
    Audit Detail rows: exactly 50600 and 51569 flip Indigenous->General
    (53717 was already General beforehand); 54535/51620/54538/54484/54529
    stay Indigenous; zero other rows changed."""

    def test_row_50600_curriculum_topic_list_demotes_to_general(self):
        """Real gold row shape (ACEE 50600): 'Indigenous perspectives' is
        one item in a list of curriculum content taught to educators
        ('eco-action strategies, and Indigenous perspectives') -- a topic
        being taught, not the served population (educators/students).
        Demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "This course equips educators with the tools to teach "
                "environmental principles, climate justice, eco-action "
                "strategies, and Indigenous perspectives. The program "
                "addresses a gap in teacher education."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("topic context only", flag)

    def test_row_51569_consulted_knowledge_holders_demotes_to_general(self):
        """Real gold row shape (Exposed Wildlife Conservancy 51569):
        'Indigenous knowledge holders' are consulted as advisors alongside
        wildlife biologists and conservation experts -- a consulted-party
        mention, not the served population (municipalities/general
        public). Demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "The toolkit will guide communities on safe wildlife "
                "coexistence. We will consult wildlife biologists, "
                "conservation experts, and Indigenous knowledge holders to "
                "ensure the resource reflects the latest science and "
                "culturally relevant perspectives for municipal officials "
                "and the general public."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("topic context only", flag)

    def test_row_53717_no_indigenous_signal_stays_general(self):
        """Real gold row shape (Chronos Music Society of Alberta 53717): a
        touring music ensemble's capacity-building request carries no
        Indigenous (or other ethnic) signal at all -- plain General,
        unaffected by the G3 role-tiering change (this row was already
        General before G3; included as a regression guard)."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Chronos Vocal Ensemble's staff, board members, singers, "
                "and volunteers will invest time in planning, system-"
                "building, and process-documenting for an out-of-province "
                "touring season, including a new recording release."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)

    def test_row_54535_intersectional_served_list_stays_indigenous(self):
        """Real gold row shape (Edmonton Association of the Deaf 54535):
        an explicit list of populations continuing to use a renovated
        space -- 'seniors, disabled people, youth, families, Indigenous
        peoples, and LGBTQ community members' -- is a served-population
        list, not a topic mention. Must stay Indigenous."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Renovations will ensure seniors, disabled people, youth, "
                "families, Indigenous peoples, and LGBTQ community members "
                "continue gathering in a safe, accessible space."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_row_51620_residential_school_context_rescues_training_topic(self):
        """Real gold row shape (Boyle McCauley Health Centre/Radius
        51620): every Indigenous mention in the body is staff-training/
        topic framing ('Indigenous Awareness Training', 'Indigenous
        Perspectives workshops') with no explicit 'for Indigenous X'
        served phrase -- but the body also references residential schools
        and Truth and Reconciliation, which rescues the row (the training
        exists so staff can better serve a population affected by that
        history). Must stay Indigenous, not fall to General."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Staff will receive Indigenous Awareness Training and "
                "attend Indigenous Perspectives workshops. A large number "
                "of the population we serve have been impacted by "
                "historical trauma and the adverse impacts of residential "
                "schools, and this training supports our contribution to "
                "Truth and Reconciliation efforts in our community."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_row_54538_explicit_served_frame_survivors_stays_indigenous(self):
        """Real gold row shape (HERizon Healing Society 54538): 'justice
        navigation services for Indigenous Survivors of exploitation' is
        an explicit served-frame mention ('services for Indigenous X').
        Must stay Indigenous."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "The Federal Department of Justice approved a grant for "
                "justice navigation services for Indigenous Survivors of "
                "exploitation and trafficking, alongside cultural healing, "
                "teachings, and ceremony for all survivors served."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_row_54484_served_youth_and_ceremony_stays_indigenous(self):
        """Real gold row shape (Mountain Plains Family Service Society
        54484): 'unique needs of Indigenous youth' is a served-population
        mention, and the body also references ceremony (drumming,
        storytelling) -- both preserve the classification. Must stay
        Indigenous."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "This mentorship initiative gives particular attention to "
                "the unique needs of Indigenous youth. All activities will "
                "be guided by a Cultural Advisor, ensuring Indigenous "
                "traditions and protocols are honored through drumming, "
                "storytelling, and ceremony."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_row_54529_provider_mention_rescued_by_served_list(self):
        """Real gold row shape (Canadian Digestive Health Foundation
        54529): 'Sharon Swampy, Indigenous Nutritionist' is a
        provider-role mention (demoted on its own), and 'Esquao Institute
        for the Advancement of Aboriginal Women' is a partner org name --
        but the body elsewhere explicitly names Indigenous residents as a
        served population ('to serve Edmonton's Indigenous ...
        populations'), which rescues the group per the existing
        served-frame-wins-dedup rule. Must stay Indigenous."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Workshops led by local registered dietitians, including "
                "Sharon Swampy, Indigenous Nutritionist, in partnership "
                "with Esquao - Institute for the Advancement of Aboriginal "
                "Women, bring cultural relevance to serve Edmonton's "
                "Indigenous and Ethnocultural populations."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")


class TestBipocGrantNameAndNorthAmericanKeyword(unittest.TestCase):
    """Batch-2 spurious-match fixes: 'BIPOC' as a grant/program name is not a
    served BIPOC signal; the over-broad 'north american' keyword is dropped."""

    def test_bipoc_grant_name_is_not_a_served_signal(self):
        from ethnic_taggerv3 import is_bipoc_real_target
        # Naming the funding stream — not a served population.
        self.assertFalse(is_bipoc_real_target(
            "the bipoc grant will support our filipino parenting program"))
        self.assertFalse(is_bipoc_real_target(
            "the ecf bipoc grant would allow us to serve newcomer families"))
        self.assertFalse(is_bipoc_real_target(
            "we are piloting a bipoc media lab for local creators"))

    def test_genuine_bipoc_population_still_counts(self):
        from ethnic_taggerv3 import is_bipoc_real_target
        self.assertTrue(is_bipoc_real_target("a program for bipoc youth in edmonton"))
        self.assertTrue(is_bipoc_real_target("supporting bipoc women entrepreneurs"))
        # Grant-name occurrence AND a genuine served mention -> still True.
        self.assertTrue(is_bipoc_real_target(
            "the bipoc grant funds workshops led by bipoc artists"))

    def test_bipoc_grant_with_specific_group_classifies_that_group(self):
        # Real gold row Edmonton Philippine Centre 51591: "The BIPOC Grant"
        # names the funding; the served population is Filipino families ->
        # Asian/Filipino, not Multiple.
        e1, e2, e3, flag = classify_row(
            row(
                name="Edmonton Philippine International Centre",
                desc=("The BIPOC Grant will support our Filipino bicultural "
                      "parenting program, co-created with Filipino parents."),
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "Asian Origins")
        self.assertEqual(e3, "Filipino")

    def test_north_american_keyword_is_dropped(self):
        # Real gold row Black Health Initiative 51615: "North American context"
        # must not match a taxonomy keyword (it did, forcing Multiple).
        import pandas as pd
        from ethnic_taggerv3 import build_taxonomy, TAXONOMY_ALL_TERMS
        df = pd.DataFrame({TAXONOMY_ALL_TERMS: [
            "North American Origins",
            "North American Indigenous Origins",
            "Asian OriginsEast and Southeast Asian OriginsFilipino",
        ]})
        kws = {e["keyword"] for e in build_taxonomy(df)}
        self.assertNotIn("north american", kws)
        self.assertIn("north american indigenous", kws)
        self.assertIn("filipino", kws)


class TestG6IndigenousTopicPartnerDemotion(unittest.TestCase):
    """Plan.md Chunk G6 (hybrid policy): splits the non-served Indigenous
    pattern-path mentions G3 lumped into one weak "topic" role into two
    outcomes. DEMOTE to General: a provider/consultant role noun
    (consultant/advisor/liaison), or an aspirational "hopes to/wants to
    reach/include" claim -- neither names a currently-served population.
    KEEP Indigenous + FLAG_INDIGENOUS_TOPIC_VERIFY: Indigenous knowledge/
    art/practice integrated as actual program content ("Indigenous
    wisdom"/"dance"), or an Indigenous community/nation named as an active
    partner ("in collaboration with"/"seek partnerships ... with") -- ambiguous,
    but not clearly non-served either, so classification is unaffected and
    only a review flag is added.

    Verified over all 448 live Audit Detail rows: exactly 54491 (Skills
    Society) and 50691 (WILDNorth) flip Indigenous->General; 50616 (Canadian
    Wildlife Federation) and 50671 (Sierra Club) stay Indigenous and gain
    FLAG_INDIGENOUS_TOPIC_VERIFY; every must-keep row (54535, 51620, 54538,
    54484, 54529, 50606, 54681, 50621, 50673, 51589, 51581, 52473, 54544,
    51624, 54694, 51613, 50328, 54686, 49327, 50607, 54685, 51625, 50681,
    54528) and the already-General 50600/51569 are unchanged; zero other
    rows changed."""

    def test_row_54491_consultant_to_integrate_demotes_to_general(self):
        """Real gold row shape (Skills Society 54491): an "Indigenous
        consultant to integrate Indigenous knowledge and practices" is
        hired expertise applied to the org's OWN internal model, not a
        claim about who the org serves. Both Indigenous mentions in this
        clause demote (the second is the direct object of the same
        "consultant to integrate" clause). Demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Funds will support a Research and Development lead to "
                "test and refine the model, and an Indigenous consultant "
                "to integrate Indigenous knowledge and practices into our "
                "apartment support model for tenants with disabilities."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("provider context only", flag)

    def test_row_50691_wants_to_include_more_demotes_to_general(self):
        """Real gold row shape (WILDNorth 50691): "wants to expand ...
        include more indigenous and marginalized communities, hoping to
        double its reach" is an aspirational-reach claim about a FUTURE
        audience, not the population currently served. Demotes to
        General."""
        e1, e2, e3, flag = classify_row(
            row(
                summary=(
                    "The organization wants to expand and hone their "
                    "programming and include more indigenous and "
                    "marginalized communities, hoping to double its reach "
                    "in the Edmonton area."
                ),
                purpose=(
                    "To expand and hone programming to include more "
                    "indigenous and marginalized communities, doubling the "
                    "reach in the Edmonton area."
                ),
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("aspirational context only", flag)

    def test_row_50616_indigenous_wisdom_as_content_stays_indigenous_and_flags(self):
        """Real gold row shape (Canadian Wildlife Federation 50616):
        "integrate science-based knowledge and Indigenous wisdom" and
        "partnerships with schools, NGOs and Indigenous communities" are
        both topic-content/partnership framings -- ambiguous, so the
        classification stays Indigenous but gains
        FLAG_INDIGENOUS_TOPIC_VERIFY."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "CCNE will integrate science-based knowledge and "
                "Indigenous wisdom to inspire environmental stewardship. "
                "Through partnerships with schools, NGOs, and Indigenous "
                "communities, CCNE will foster environmental literacy."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertIn("Indigenous topic/partnership mention", flag)

    def test_row_50671_partnership_with_indigenous_nations_stays_indigenous_and_flags(self):
        """Real gold row shape (Sierra Club 50671): "Indigenous Nations
        engagement/consultations" and "seek partnerships and collaboration
        with Indigenous Peoples" are both partnership framings -- stays
        Indigenous, gains FLAG_INDIGENOUS_TOPIC_VERIFY."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Key initiatives include Indigenous Nations engagement/"
                "consultations: we will seek partnerships and collaboration "
                "with Indigenous Peoples, which is vital for integrating "
                "land-based learning."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertIn("Indigenous topic/partnership mention", flag)

    def test_liaison_provider_role_demotes_alone(self):
        """New provider-role noun added in G6 (not covered by G3): an
        Indigenous liaison hired to advise the org, with no other
        Indigenous signal in the body, demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(desc="The project team includes an Indigenous liaison to advise on protocol."),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)

    def test_row_54681_engagement_toward_launching_program_stays_indigenous_no_flag(self):
        """Real gold row shape (Ben Calf Robe Society 54681): "community
        engagement toward launching an Indigenous Head Start/early
        learning program for children aged 3-5" is an explicit
        served-population program description -- the bare word
        "engagement" nearby must NOT trigger the G6 partnership flag on
        an otherwise clearly-served mention (regression guard for a false
        positive caught during G6 verification)."""
        e1, e2, e3, flag = classify_row(
            row(purpose=(
                "To conduct consulting and community engagement toward "
                "launching an Indigenous Head Start/early learning program "
                "for children aged 3-5."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertNotIn("Indigenous topic/partnership mention", flag)


class TestG7FictionalSettingAndSpuriousTokenCollisions(unittest.TestCase):
    """Plan.md Chunk G7: an ethnic/national term that names the SETTING of
    a story/myth/themed event (not a real served population), or that
    collides with an unrelated common word sharing the same spelling
    ("polish" as in "final polish"), must not classify. The story-setting
    guard (ROLE_SETTING_BEFORE/AFTER_PATTERNS) is generic across every
    group EXCEPT the "a [X] festival" frame, which is scoped to the
    "byzantine" ALWAYS_MULTIPLE_COMPOUNDS entry only (a real ethnocultural
    org's own "[Ethnicity] ... Festival" -- e.g. "Ukrainian Dance
    Festival" -- is a genuine served-identity claim, not a themed setting;
    see extract_compound_candidates in extractors.py).

    Verified over all 448 live Audit Detail rows: exactly 51022/54504
    (Theatre Prospero), 54622 (Arts On The Ave), 51570 (Garneau), and
    54505 (Thousand Faces) flip/improve; zero other rows changed (in
    particular 54137 Ukrainian Cheremosh Dance Ensemble, whose "Ukrainian
    Dance Festival" mention must NOT be caught by the byzantine-specific
    festival guard, stays unchanged)."""

    TAXONOMY_POLISH = TAXONOMY + [{
        "keyword": "polish",
        "level1": "European Origins",
        "level2": "Eastern European Origins",
        "level3": "Polish",
        "depth": 3,
    }]

    def test_row_51022_egyptian_story_setting_demotes_to_general(self):
        """Real gold row shape (Theatre Prospero 51022): "an Egyptian
        story about a Prince doomed at birth" names the SETTING of a
        devised play, not a served population. The story/myth noun
        trails the term here ("Egyptian story about"), exercising the
        AFTER variant of the setting-frame guard. Demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(summary=(
                "Audience participants 'play' most or all of the parts in "
                "an Egyptian story about a Prince doomed at birth to die "
                "by Snake, Dog, or Crocodile."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("topic context only", flag)

    def test_row_54504_egyptian_myth_demotes_but_treaty6_children_stays_indigenous(self):
        """Real gold row shape (Theatre Prospero 54504): TWO Egyptian
        mentions ("based on the incomplete tale of an Egyptian prince";
        "based on an Egyptian myth about a Prince") both demote via the
        BEFORE setting-frame guard ("based on"), but "Treaty 6 children"
        elsewhere in the same row is a genuine geographic/served reference
        to real children, not a setting -- must stay Indigenous, not
        Multiple and not General."""
        e1, e2, e3, flag = classify_row(
            row(
                desc=(
                    "Two casts of actors will learn the play THE DOOMED "
                    "PRINCE, based on the incomplete tale of an Egyptian "
                    "prince doomed to die by snake, dog, or crocodile."
                ),
                summary=(
                    "Hundreds of Greater Edmonton Area and Treaty 6 "
                    "children will learn and enact a fun play based on an "
                    "Egyptian myth about a Prince fated to die by Snake, "
                    "Dog, or Crocodile."
                ),
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")

    def test_byzantine_winter_festival_setting_demotes_to_general(self):
        """Real gold row shape (Arts On The Ave 54622): "Deep Freeze: A
        Byzantine Winter Festival" names a themed/branded winter festival,
        not an actual Byzantine-heritage population. Demotes to General
        (was previously Multiple via the ALWAYS_MULTIPLE_COMPOUNDS entry)."""
        e1, e2, e3, flag = classify_row(
            row(purpose=(
                "To purchase new winterized trapper tents to use during "
                "the Deep Freeze: A Byzantine Winter Festival after "
                "discovering the existing tents have mold damage."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)

    def test_byzantine_without_festival_frame_still_produces_multiple(self):
        """Regression guard: the byzantine-specific festival demotion must
        NOT affect a bare 'Byzantine cultural heritage community' mention
        with no festival framing -- still Multiple (unchanged existing
        behavior, see TestBlueprint2Fixes.test_byzantine_produces_multiple)."""
        e1, e2, e3, flag = classify_row(
            row(desc="Programming for the Byzantine cultural heritage community."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)

    def test_ukrainian_dance_festival_not_caught_by_byzantine_festival_guard(self):
        """Regression guard (caught during G7 verification): a REAL
        ethnocultural org's own "[Ethnicity] Dance Festival" (Ukrainian
        Cheremosh Dance Ensemble Society 54137's "Cheremosh Ukrainian
        Dance Festival") must NOT be demoted -- the "a [X] festival"
        setting frame is scoped to the byzantine compound only, not applied
        generically to every group's own festival name."""
        e1, e2, e3, flag = classify_row(
            row(
                summary="The Cheremosh Ukrainian Dance Festival is hosting its 40th anniversary event.",
                purpose="To fund new dance medals for the 40th anniversary Cheremosh Ukrainian Dance Festival.",
            ),
            TAXONOMY_G2,
        )
        self.assertEqual(e1, "European Origins")
        self.assertEqual(e3, "Ukrainian")

    def test_final_polish_does_not_classify_as_polish(self):
        """Real gold row shape (Garneau Community League 51570): "final
        polish for public release" is a post-production editing term, not
        the Polish people. This occurrence must be skipped entirely (not
        even a weak candidate) -- General with no ethnic flag at all."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Post-production will involve editing the footage, "
                "including sound mixing, music, motion graphics, and "
                "final polish for public release."
            )),
            self.TAXONOMY_POLISH,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertEqual(flag, "")

    def test_genuine_polish_mention_still_classifies(self):
        """Regression guard: the 'final polish' stoplist must not swallow
        a genuine Polish-community mention elsewhere in the same body."""
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting Polish newcomer families settling in Edmonton."),
            self.TAXONOMY_POLISH,
        )
        self.assertEqual(e1, "European Origins")
        self.assertEqual(e3, "Polish")

    def test_row_54505_partner_org_name_council_of_india_societies_stays_general(self):
        """Real gold row shape (Thousand Faces Festival 54505): "in-kind
        community support from Council of India Societies" names a THIRD-
        PARTY partner organization, not the Thousand Faces Festival's own
        served population. The org-name-after guard now also matches the
        plural "Societies" (previously only singular "Society"), so this
        occurrence is tagged org_name (weak) instead of defaulting to
        served. Demotes to General."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "ECF's investment leverages annual support from TD Bank "
                "and the Canadian Multicultural Education Fund, plus "
                "substantial in-kind community support from Council of "
                "India Societies and the Edmonton Newcomer Centre."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertIn("org_name context only", flag)


class TestG8GazaPalestinianMapping(unittest.TestCase):
    """Plan.md Chunk G8: "Gazan"/"Gaza" are demonyms for Gaza that aren't a
    taxonomy keyword on their own (only "Palestinian" is the real L3 term),
    so a row that only ever says "Gazan" fell through to General with no
    ethnic signal at all. Added to COUNTRY_REGION_MAP -> Asian Origins /
    West and Central Asian and Middle Eastern Origins / Palestinian, same
    L1/L2/L3 as the existing Canada-Palestine row (50613).

    Verified over all 448 live Audit Detail rows: exactly one row changes
    (54545 Penny Appeal Canada, General -> Palestinian); zero regressions."""

    def test_row_54545_gazan_newcomers_maps_to_palestinian(self):
        """Real gold row shape (Penny Appeal Canada 54545): "help Gazan
        newcomers build stability" / "support Gazan newcomers through
        trauma-informed mental health services" -- a genuine served-
        population claim, previously unmapped and falling to General."""
        e1, e2, e3, flag = classify_row(
            row(
                desc=(
                    "Penny Appeal Canada is implementing a focused "
                    "initiative in Edmonton to help Gazan newcomers build "
                    "stability, connection, and resilience."
                ),
                summary=(
                    "Penny Appeal Canada is launching a community-based "
                    "program in Edmonton to support Gazan newcomers "
                    "through trauma-informed mental health services, peer "
                    "support, and welcoming hubs."
                ),
                purpose=(
                    "To launch a trauma-informed program supporting Gazan "
                    "newcomers with mental health services, peer support, "
                    "and anti-racism workshops."
                ),
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "Asian Origins")
        self.assertEqual(e2, "West and Central Asian and Middle Eastern Origins")
        self.assertEqual(e3, "Palestinian")

    def test_from_gaza_phrase_also_maps_to_palestinian(self):
        """"from Gaza" (Case 7 prepositional form) resolves the same as the
        bare "Gazan" demonym."""
        e1, e2, e3, flag = classify_row(
            row(desc="Supporting newcomer families from Gaza settling in Edmonton."),
            TAXONOMY,
        )
        self.assertEqual(e1, "Asian Origins")
        self.assertEqual(e3, "Palestinian")


class TestG9FlagTextCleanup(unittest.TestCase):
    """Plan.md Chunk G9: reporting-quality-only flag text fixes; neither
    changes any classification outcome.

    1. The "pattern" source flag ("Pattern rule match (Directional Region,
       e.g. North African)") was stamped on North American Indigenous rows
       too, since Indigenous terms (indigenous/aboriginal/metis/treaty 6/...)
       also flow through PATTERN_RULES -- wrong label. Indigenous now gets
       its own flag text, keyed on level1 in source_flag().
    2. The Step 2b "Review: multiple distinct groups detected..." flag on
       the is_black and (is_african|is_caribbean) branch is dropped as pure
       noise, matching Step 3's existing Fix 4 treatment (rows 120, 164,
       229, 358 in the live Audit Detail sheet).

    Verified over all 448 live Audit Detail rows: 42 flag-text-only flips
    (38 Indigenous-pattern relabels + 4 stale-flag removals -- see
    TestSprint2Fixes.test_somali_and_black_produces_multiple_no_generic_flag
    above for the Black+African case), plus the one real G8 classification
    flip; zero classification regressions elsewhere."""

    def test_indigenous_pattern_match_gets_own_flag_text(self):
        """A bare "aboriginal" pattern match (not a taxonomy fixture
        keyword, so it resolves via PATTERN_RULES source "pattern") must
        not carry the African-specific "Directional Region, e.g. North
        African" label."""
        e1, e2, e3, flag = classify_row(
            row(desc="Programming and supports for Aboriginal youth in Edmonton."),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertIn("General Indigenous term matched", flag)
        self.assertNotIn("Regional phrase matched", flag)

    def test_directional_region_pattern_flag_unchanged_for_non_indigenous(self):
        """Regression guard: a genuine directional-region pattern match
        (e.g. "North African") keeps its own distinct flag text -- only the
        Indigenous branch gets the "General Indigenous term matched" label."""
        e1, e2, e3, flag = classify_row(
            row(desc="Support for North African newcomer families in Edmonton."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertIn("Regional phrase matched", flag)


class TestG11AllyshipDemotion(unittest.TestCase):
    """Plan.md Task 4 (G11): a general-community request that merely frames
    itself as an "ally to indigenous people" / expresses support for
    "reconciliation" was classified North American Indigenous Origins with
    full confidence and NO review flag -- an allyship/reconciliation
    statement names the org's own relationship to the group, not a served
    population claim.

    Stakeholder-decided fix (2026-07-15): KEEP Indigenous (do not demote to
    General), but ADD a review flag. The allyship frame demotes only the
    specific "ally to X" occurrence from role "served" to weak "topic"; a
    separate genuine topic/partnership occurrence elsewhere in the same row
    (e.g. "indigenous knowledge" integrated as program content) still
    resolves as "topic_keep", so the row stays Indigenous overall but now
    carries FLAG_INDIGENOUS_TOPIC_VERIFY instead of silent confidence."""

    def test_nature_trail_ally_framing_stays_indigenous_but_gets_verify_flag(self):
        """Representative row: a parkland/rewilding trail project whose only
        Indigenous mentions are "indigenous knowledge" (topic content) and
        "an ally to indigenous people ... contribute to reconciliation"
        (allyship framing) -- no actual Indigenous served population named
        anywhere in the text."""
        e1, e2, e3, flag = classify_row(
            row(
                desc=(
                    "Interpretive signage will teach visitors about the "
                    "parkland ecoregion, indigenous knowledge, and native "
                    "plant species along the trail."
                ),
                summary=(
                    "This project offers an opportunity to be an ally to "
                    "indigenous people and contribute to reconciliation and "
                    "climate change solutions through community rewilding."
                ),
                purpose="To restore native habitat and build public trail infrastructure.",
                name="River Valley Rewilding Initiative",
            ),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertIn("Indigenous topic/partnership mention", flag)

    def test_genuinely_served_indigenous_row_not_affected_by_allyship_frame(self):
        """Regression guard: an "ally to indigenous people" mention must NOT
        demote a row that ALSO contains a genuine served-population claim
        elsewhere (e.g. "programming for Indigenous youth") -- the served
        occurrence still wins, no verify flag needed."""
        e1, e2, e3, flag = classify_row(
            row(desc=(
                "Our organization strives to be an ally to indigenous "
                "people. We deliver after-school programming for Indigenous "
                "youth in the community."
            )),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertNotIn("Indigenous topic/partnership mention", flag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
