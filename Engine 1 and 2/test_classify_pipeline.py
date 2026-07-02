import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from classify_pipeline import classify_row
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
        self.assertIn("multiple distinct groups", flag)

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
        self.assertIn("Country/nationality", flag)

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
        self.assertIn("Pattern rule", flag)

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
        self.assertIn("multiple distinct groups", flag)

    # ------------------------------------------------------------------
    # 6. BIPOC alone (no other ethnic signal)
    # ------------------------------------------------------------------
    def test_bipoc_alone(self):
        """
        BIPOC with no other ethnic keyword produces MULTIPLE and a
        'BIPOC signal detected' flag.  No specific group is named.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Services designed for BIPOC youth in the community."),
            TAXONOMY,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("BIPOC signal detected", flag)

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
        General Population and appends an annotation note — it does NOT
        short-circuit classification before other evidence is weighed.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="A multicultural community event for all residents."),
            TAXONOMY,
        )
        self.assertEqual(e1, GENERAL_POP)
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("Ambiguous equity term with no paired ethnic signal", flag)

    # ------------------------------------------------------------------
    # 9. Ambiguous equity word WITH a paired ethnic signal
    # ------------------------------------------------------------------
    def test_grassroots_with_signal_classifies_normally_and_flags(self):
        """
        An AMBIGUOUS_EQUITY_WORD alongside a real ethnic signal does NOT
        block classification — the signal wins and an annotation is added.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="A multicultural program focused on the Somali community."),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        self.assertIn("buzzword", flag)

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
        self.assertIn("Negation detected", flag)

    # ------------------------------------------------------------------
    # 13. Organization name fallback (last resort)
    # ------------------------------------------------------------------
    def test_org_name_fallback(self):
        """
        When no taxonomy/pattern/country/compound signal is present,
        a known organization name resolves the row via last-resort lookup.
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Support through Bent Arrow programs for participants."),
            TAXONOMY,
        )
        self.assertEqual(e1, "North American Indigenous Origins")
        self.assertEqual(e2, "")
        self.assertEqual(e3, "")
        self.assertIn("organization name lookup", flag.lower())

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
        When the group name in the Funding Request Name IS recognized by
        the extractors (e.g. "Somali Cultural Association" — 'Somali' is
        a taxonomy keyword), the ethnocultural org flag is NOT emitted.
        Classification proceeds normally from the recognized keyword.
        """
        e1, e2, e3, flag = classify_row(
            row(name="Somali Cultural Association"),
            TAXONOMY,
        )
        self.assertEqual(e1, "African Origins")
        self.assertEqual(e2, "Southern and East African Origins")
        self.assertEqual(e3, "Somali")
        self.assertNotIn("Potential ethnocultural organization name", flag)

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
    # S7. Somali + Black → Multiple + umbrella sub-flag
    # ------------------------------------------------------------------
    def test_somali_and_black_produces_multiple_with_umbrella_flag(self):
        """
        "Somali project for Black Muslim communities" — Somali (African Origins)
        + Black (Other Ethnic) → umbrella sub-flag, not generic "distinct groups".
        """
        e1, e2, e3, flag = classify_row(
            row(desc="Somali project aims to strengthen cultural pride for Black Muslim communities."),
            TAXONOMY_S2,
        )
        self.assertEqual(e1, MULTIPLE_ETHNIC)
        self.assertIn("umbrella term (Black)", flag)

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
        self.assertIn("Country/nationality", flag)

    # ------------------------------------------------------------------
    # S10. "French Canadian Association" → ethnic kept (not language flag)
    # ------------------------------------------------------------------
    def test_french_canadian_association_keeps_ethnic_signal(self):
        """
        A named French ethnic/cultural org matches FRENCH_ETHNIC_KEEP_PATTERNS
        → the French filter does NOT drop the candidate.
        French taxonomy match should survive → European Origins.
        """
        e1, e2, e3, flag = classify_row(
            row(name="French Canadian Association of Alberta"),
            TAXONOMY_S2,
        )
        self.assertNotEqual(e1, GENERAL_POP)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
