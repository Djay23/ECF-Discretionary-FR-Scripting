# Classification Engine — Case Analysis & Execution Blueprint (handoff to Sonnet)

**Sources analyzed:** `Taxonomy/audit_gold_audited.xlsx` (gold standard, 448 rows), `Taxonomy/review_report(Gender and Sex).xlsx` (row context + flag/class frequency tabs), `Taxonomy/Taxonomy - Definitions.xlsx` (Ethnic/Gender/Sexual taxonomies). Production paths: ethnic → `classify_pipeline.classify_row` → `resolver.resolve`; gender/sex → `Gender_SexID.classify_gender` / `classify_sexual`. (`ethnic_taggerv3.classify_row` is dead code — do not edit it.)

---

## Step 1 — Discrepancy Matrix

The auditor deep-reviewed **113 of 448 rows** (filled the `Correct *` columns); the other 335 are blank (treated as engine-correct/unreviewed). Agreement is computed on canonicalized labels (General-Population variants folded; engine's `Ethnic 2/3` counted, since the gold collapses the answer into one `"L1 - L2"` string; accents/parentheticals folded).

| Axis | Auditable rows | Agreement | Disagreements |
|---|---|---|---|
| **Ethnic** | 37 (usable corrections)¹ | **86.5%** (32/37) | 5 |
| **Gender** | 113 | **90.3%** (102/113) | 11 |
| **Sexual** | 113 | **99.1%** (112/113) | 1 |

¹ Only 37 of the 113 filled ethnic cells are usable — **76 hold a wrong dropdown value** (a *gender* label pasted into the ethnic column). See Step 3.

**Top disagreement categories (quantified):**

1. **Gender "Women and/or girls" over-triggered → should be General — 5 cases (45% of gender errors).** Signal lives only in the org name: *Wardrobe for Women*, *Alberta Immigrant Women & Children* (body is about African youth), *Black Canadian Women in Action*, *Swan Women's*.
2. **Gender "Multiple gender identities" over-triggered → should be General — 3 cases (27%).** *Boys & Girls Clubs Big Brothers Big Sisters* — "boys/girls/brothers/sisters" in the org name only.
3. **Ethnic "Multiple Ethnic" over-triggered → should be single group — 3 cases (60% of ethnic errors).** Black+African conflation: *Council for the Advancement of African Canadians* ×2 → `Other Ethnic: Black`; *Alberta Ballet* → `African Origins`.
4. **"gender-diverse" unhandled → wrong bucket — 3 cases** (gender: *John Humphrey* ×2 `Other`→`Multiple`, *Elizabeth Fry* `Women`→`Multiple`; sexual: *Elizabeth Fry* `General`→`2SLGBTQIA+`).
5. **Known-org / empty body — 1 case.** *Niginan Housing Ventures* `General`→`North American Indigenous Origins`.

**Directional signature (the systemic bias):** disagreements are **~85% false positives / over-classification** — the engine assigns a specific group (or Multiple) when the served population is actually General or a single group. Under-calls are rare (Niginan; Elizabeth Fry sexual). The root is always the same: **a term that is present in the text but does not describe the served population.**

**Isolated edge/boundary cases** (the exact triggers):
- Identity term bound in the **applicant/partner org name** ("Council for the Advancement of African **Canadians**", "**Boys & Girls** Clubs", "in partnership with **Africa** Centre").
- Identity term describing a **service provider**, not a beneficiary ("Sharon Swampy, **Indigenous** Nutritionist" — Digestive Health).
- Identity term inside a **proper-noun descriptor** ("the first **Black** classical ballet company" — Alberta Ballet).
- **Unmodeled vocabulary**: "gender-diverse"; French "femme"; possessive-plural "Womens'".
- **Silent suppression**: `2SLGBTQIA+` inside "for example, …" dropped with no trace (Autism 54463, CMHA 54531).

---

## Step 2 — Root Cause Investigation

**A. Semantic ambiguity (word means different things to engine vs human).**
- "Black" = served population **vs** proper-noun descriptor ("Black classical ballet company"). Engine has no served-vs-descriptor sense.
- "African Canadian(s)" — a single identity token the engine can split/relocate; and "African" appearing in a partner org name reads as a served signal.
- "femme" = French *woman* vs coded 2SLGBTQIA term; engine models neither.
- "gender-diverse" — a distinct concept (→ Multiple gender + 2SLGBTQIA+) that the engine collapses into a single `Other` key.

**B. Overly rigid regex / hardcoded boundaries.**
- `\bwomen\b` fails on normalized `"womens"` (from `"Womens'"`) → *Edmonton Women's Shelter* not even detected (`gender_constants.py:73-126`).
- `IDENTITY_PHRASE_REWRITES` and org-context patterns miss plurals ("Boys & Girls **Clubs**" — the `\bclub\b` boundary misses the plural, so `FLAG_ORG_NAME` never fires; `gender_constants.py:167-178`).
- `BIPOC_KEYWORDS` has a **missing-comma bug** (`constants.py:122-123`) concatenating `\bibpoc\b` + `\bpeople of colou?r\b` → "people of colour" is never matched, silently under-detecting a core BIPOC→Multiple rule.
- Distinct-L1 → Multiple (`resolver.py:178-184`) is a hard count with no notion of umbrella-vs-specific or evidence role.

**C. Human bias / inconsistent labeling (engine may be right).**
- **The gold file is dirty**: 76 ethnic cells carry a gender label (Step 3) — those "mismatches" are data entry, not engine error.
- *Edmonton Women's Shelter*: auditor flip-flops — note on 50630 says "should be Women", note on 54130 says "Women unless extra info", yet *Wardrobe for Women* note says "General". Genuinely inconsistent human policy → we standardize to **General + flag** (D1).
- Asian L2 label variance (`West and Central Asian **and Middle Eastern** Origins` vs gold `West and Central Asian Origins`) — a taxonomy-string mismatch, engine arguably correct.
- Autism 54463 `2SLGBTQIA+` in "for example" — engine correctly suppressed; auditor ambivalent ("wouldn't have minded"). Engine right; the gap is **transparency**, not correctness.

**D. Missing contextual features the engine can't see.**
- **Evidence role** of each signal: *served population* vs *org name* vs *service provider* vs *partner* vs *example/aspirational/negated*. This single missing feature explains categories 1–3 and 60%+ of all disagreements.
- **Known-organization identity** (Niginan Housing = Indigenous) — world knowledge absent from the text.
- **Cross-column provenance** — whether a signal is corroborated in the body or lives only in the name.

---

## Step 3 — Systemic / Data-Quality Problems (beyond engine-vs-human gaps)

- **Dirty gold labels (systemic):** **76/113** filled `Correct Ethnic 1` cells contain the string `"General Population (No specific gender served)"` — a *gender* dropdown value in the *ethnic* column. Any exact-match scorer (`audit_score.py`) counts these as ethnic errors, **inflating the apparent ethnic error rate ~15×**. Must be canonicalized before scoring (Fix 5).
- **Unusable flag calibration:** the `Ethnic/Gender/Sexual Flag OK?` columns are **blank on all 448 rows**. There is no statistical basis to tune flags; all flag decisions in this plan rest on the free-text `Notes`. (Recommend the next audit pass actually fill Flag-OK.)
- **Null / thin inputs → default classifications:** 4 rows have empty Project+Summary and a thin Purpose (e.g. *Niginan*, *Autism 52471*) → the engine has only the name to go on, which is exactly where name-only misfires originate. These must degrade to General + flag (not silently to a name-driven label).
- **Cascade / consistency risk:** **84 orgs have multiple funding requests** (e.g. *Council for African Canadians* appears 12×, classified as African / Multiple / Black across its rows; *Alberta Ballet* 51597 Multiple vs 54462 African for the **same program**). One brittle rule (the "Black classical ballet company" token) flips an entire program's classification between near-identical rows. Fixing evidence-role tiering removes this instability; a consistency check across same-org rows is a useful safety net.
- **Encoding:** flag strings use an em-dash that renders as `�` in the frequency tabs — cosmetic, but confirm UTF-8 on write so report tabs are clean.

---

## Step 4 — Architectural Blueprint (for Sonnet)

**Decisions locked with the stakeholder (do not re-litigate):**
- **D0 architecture is phased:** Phase 1 (name-vs-body split) then Phase 2 (evidence-role tiering).
- **D1** name-only signal → General + flag; curated known-org map is the only exception (Niginan; existing Bent Arrow/Treaty 6). *Edmonton Women's Shelter is NOT curated → General + flag, same as Wardrobe for Women.*
- **D2** Black + African both genuinely served → **Multiple Ethnic** + review flag (never interchangeable).
- **D3** Black-as-descriptor: Phase 1 leaves Alberta Ballet as Multiple+flag; **Phase 2 supersedes** → reclassifies to `African Origins` (matches gold).
- **D4** remove 4 noise flags (Fix 4); gate context-only flags (Fix 6); flag suppressed signals (Fix 7).

### Fix 1 — Anti-misclassification architecture (RC-D; the core work)

**Phase 1 — Name/body column split.** Files: `ethnic_taggerv3.py`, `classify_pipeline.py`, `Gender_SexID.py`, `constants.py`.
- In `ethnic_taggerv3.py` add `get_body_and_name_texts(row)` returning `(body_text, name_text)` from `BODY_COLS = [Final_Project_Description, Final_Summary_Description, Purpose]` and `NAME_COL = Funding Request Name`, each normalized + rewritten exactly as `get_column_texts` does today (`ethnic_taggerv3.py:585`); redefine `get_column_texts` as their concatenation so existing callers are unaffected.
- **Ethnic** (`classify_pipeline.classify_row`, `:146-245`): run the six extractors (`:168-175`) and `is_bipoc_real_target` on `body_text`; run a lightweight extraction on `name_text` only for the known-org check + name-only flag. Known-org match (`ORG_NAME_ETHNICITY_MAP`, `constants.py:189`) classifies definitively. If body has no candidates but the name does (or BIPOC came only from the name) and no known-org → `GENERAL_POP` + new flag `"Signal appears only in the organization/funding-request name - classified General; verify served population"`. Otherwise `resolve(body_states,…)`.
- **Gender/Sex** (`Gender_SexID.classify_gender` `:211`, `classify_sexual` `:295`): extract from `body_text`; if body has keys → classify; if body empty but `name_text` has a term → General label + reuse `FLAG_ORG_NAME` (`gender_constants.py:146`). Drop `is_org_name_context` gating of *classification* (it only informs the flag now).
- Add `Niginan Housing Ventures → North American Indigenous Origins` to the known-org map.
- **Tests to update:** any `row(name=…)`-only test that currently expects a specific label (e.g. `test_institute_for_women_classified_and_flagged`) → now General + flag. Body-signal tests (e.g. `test_org_flag_not_fired_for_plain_gender_description`) stay classifying.

**Phase 2 — Evidence-role tiering** (catches org/provider/example mentions *inside* the body: Digestive Health, Good Women Dance, Alberta Ballet). Files: `extractors.py`, `resolver.py`, `Gender_SexID.py`.
- Add a `role` to each candidate (`extractors.py:38-45`) computed from the matched span's surrounding window (reuse the span helpers behind `is_negated`/`is_example_mention`, `ethnic_taggerv3.py:175,182`):
  - `served` (strong, default): beneficiary frames — "for/serving/support(ing)/empower(ing) [identity]", "[identity] (youth|families|participants|clients|community|students|residents|members)".
  - `org_name` (weak): `[identity] … (Institute|Association|Society|Centre|Center|Foundation|Council|Collaborative|Coalition|Club|Network|Group|Company|Troupe|Theatre|Ballet)`, or after `in partnership with / in collaboration with / together with / presented by`.
  - `provider` (weak): `[identity] (nutritionist|dietitian|professional|facilitator|instructor|elder|advisor|consultant|artist|teacher)` and `led by / delivered by / facilitated by [identity]`.
  - `example` / `aspirational` / `negated` (weak): reuse existing phrase banks.
- **Resolve** (`resolver.resolve`, `:92`): classify from `served` candidates only. A group with **any** `served` mention is served (rescues weak same-group mentions — Council 51599 keeps `Black` via "program for Black Edmontonians" despite "delivered by Black professionals"). If only weak candidates remain → `GENERAL_POP` + transparency note (Fix 7) naming the group and its role. BIPOC/Black/Indigenous logic (Fix 3) runs on the `served` set only.
- **Guardrail:** build role-frame lists from the audit rows only; every Phase-2 rule needs a regression tied to a specific gold row, including Council 51599 as the "provider does not demote when served present" counter-example.

### Fix 2 — "gender-diverse" + possessive/plural tokenization
Files: `gender_constants.py`, `Gender_SexID.py`.
- **2a:** add `\bgender[\-\s]?diverse\b` → a `gender_diverse` key that routes to `GENDER_MULTIPLE` (like the umbrella path `Gender_SexID.py:194-201`), and add it to `SEXUAL_GENDER_DIVERSE_PATTERNS` (`gender_constants.py:197`) → `2SLGBTQIA+`. Fixes Elizabeth Fry, John Humphrey.
- **2b:** broaden `\bwomen\b`→`\bwomens?\b`, `\bmen\b`→`\bmens?\b` (and audit the plural relational nouns) so `womens'`/`mens'` normalized forms are detected → *Edmonton Women's Shelter* now flags instead of vanishing.

### Fix 3 — Black/African/Indigenous resolver (mostly keep)
File: `resolver.py`. Keep Black+Indigenous → Multiple + BIPOC flag (`:158-163`) and Black+African/Caribbean → Multiple + umbrella flag (`:165-170`) — with Phase 2, these now fire only when both are `served`. Fix the `BIPOC_KEYWORDS` missing-comma bug (`constants.py:122-123`).

### Fix 4 — Remove 4 noise flags (stop emitting; leave helpers intact, no cosmetic churn)
`classify_pipeline.py`: "Ambiguous equity term with no paired ethnic signal" (`:97`), "Equity/diversity buzzword present alongside a real signal" (`:99`), "Possible consulted-party mention (expert/advisor role)" (`:102`). `resolver.py`: generic "Review: multiple distinct groups detected" (`:183`) — keep the Multiple *classification*, drop only the string. Formalize two tiers: Tier-1 review flags (no prefix), Tier-2 `Note (low priority):` informational.

### Fix 5 — Audit-scoring hygiene
File: `audit_score.py`. When scoring the **ethnic** axis, canonicalize every `"General Population (No specific …)"` variant on both sides before equality (removes the 76 phantom mismatches). Point the score/import scripts at `Taxonomy/audit_gold_audited.xlsx` (they currently hardcode `Data Sheets/audit_gold.xlsx`). Ensure UTF-8 on write.

### Fix 6 — Gate context-only flags to non-General rows
Files: `Gender_SexID.py`, `classify_pipeline.py`. Only emit Aspirational/emphasis/Hindu-style *contextual* flags when the resolved label ≠ General (kills ~10/12 Aspirational noise firings). Keep classification-relevant flags (negation, name-only, BIPOC) firing regardless.

### Fix 7 — Transparency for suppressed signals
Files: `classify_pipeline.py`, `Gender_SexID.py`. When example/negation/provider/org-name guards drop a signal, keep General but append one parametrized low-priority note, e.g. `"Note (low priority): 2SLGBTQIA+ mentioned in example/illustrative context - not classified; verify"`. Answers the recurring "why was X ignored?".

### Fix 8 — French gender terms
File: `gender_constants.py`. Add `\bfemmes?\b`→`women_girls`, `\bhommes?\b`→`men_boys`; keep existing `femme` coded-term flag. *Association Femme Moderne* (name-only) → General + flag.

---

## Validation strategy (slice of the Excel data)

Run from repo root (`bootstrap` fixes `sys.path`; close the workbooks first — Windows locks them).

1. **Regression suite:** `.venv\Scripts\python.exe -m pytest "Engine 1 and 2/test_classify_pipeline.py" -v` — extend `test_classify_pipeline.py` with **one test per gold disagreement**, using the `row()` helper, keyed to the new policy:
   - Name-only ethnic/gender → General + flag (Council body-only Black → `Other Ethnic: Black`; Wardrobe/Boys&Girls → General).
   - Phase 2: Digestive Health (provider+partner → General with demotion notes); Council 51599 (provider does NOT demote — stays Black); Alberta Ballet → `African Origins`.
   - gender-diverse (Elizabeth Fry, John Humphrey); Niginan known-org; BIPOC comma fix; Femme; `Womens'` tokenization; the 4 removed flags never appear; Aspirational gated; example-suppression note present.
2. **Full re-run vs gold slice:** run `generate_review_report.py`, then `audit_score.py` against `audit_gold_audited.xlsx`. Success criteria: ethnic ≥ current 86.5% and the 5 ethnic disagreements resolve (≥95% on the 37); gender ≥ 97% (resolve 8 name-only + 3 gender-diverse); sexual = 100%; **zero regressions** on the 32/102/112 rows the engine already gets right; the 4 removed flags absent from Flag-Frequency tabs; Aspirational flag count drops from 12 to ≤2 per axis.
3. **Consistency check (safety net):** verify same-org multi-row groups (the 84 dup orgs) no longer split classifications on near-identical text (Alberta Ballet 51597 vs 54462 should now agree).

## Out of scope / watch items
- Semantic fallback (`semantic_fallback.py`) stays annotate-only for ethnic General-Pop rows; untouched.
- Legacy `ethnic_taggerv3.classify_row` (dead) is not the production path — do not edit.
- Verify each Phase-2 role frame against its gold row; do not generalize beyond the audited evidence.
