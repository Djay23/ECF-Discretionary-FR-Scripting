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
        self.assertIn("BIPOC mentioned alongside", flag)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
