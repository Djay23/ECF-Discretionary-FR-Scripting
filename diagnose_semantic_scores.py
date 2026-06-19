import sys
import pandas as pd
import numpy as np

import ethnic_taggerv3 as et
import semantic_fallback as sf

# Claude Helper
"""
diagnose_semantic_scores.py
-----------------------------
Diagnostic tool — NOT part of the normal run. Prints the raw best-match
similarity score for every row ethnic_taggerv3.py classified as General
Population, with NO threshold applied, so you can see the real score
distribution from the actual embedding model before picking a cutoff.

This exists because SIMILARITY_THRESHOLD = 0.55 in semantic_fallback.py
was only ever tested against a crude stand-in (TF-IDF), not the real
sentence-transformers model — real neural embeddings often run much
"hotter" (higher baseline similarity even for unrelated text) than that
stand-in suggested, which is why every row may currently be clearing
the bar.

To Run:
    python diagnose_semantic_scores.py "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\Taxonomy - Definitions.xlsx" "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\FR testing.xlsx"
"""

def main():
    if len(sys.argv) < 3:
        print('Usage: python diagnose_semantic_scores.py "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\Taxonomy - Definitions.xlsx" "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\FR testing.xlsx"')

    taxonomy_filepath = sys.argv[1]
    funding_filepath = sys.argv[2]

    tax_df = pd.read_excel(taxonomy_filepath, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_filepath, sheet_name=et.DATA_SHEET, dtype=str)

    taxonomy_entries = et.build_taxonomy(tax_df)
    scope_notes = sf.build_scope_note_map(
        tax_df, et.TAXONOMY_ENTRY1, et.TAXONOMY_SCOPE_NOTES, et.safe_display)
    semantic_entries, semantic_texts = sf.build_candidate_texts(taxonomy_entries, scope_notes)
    semantic_embeddings = sf.get_taxonomy_embeddings(semantic_texts)

    model = sf.get_model()

    scores = []
    rows_checked = 0

    for idx, row in data_df.iterrows():
        e1, e2, e3, flag = et.classify_row(row, taxonomy_entries)
        if e1 != et.GENERAL_POP:
            continue  # only General Population rows reach the semantic step in the real run

        rows_checked += 1
        combined_text = " ".join(t for t in et.get_column_texts(row) if t.strip())
        if not combined_text.strip():
            continue

        query_embedding = model.encode([combined_text], normalize_embeddings=True)[0]
        sim_scores = semantic_embeddings @ query_embedding
        best_idx = int(np.argmax(sim_scores))
        best_score = float(sim_scores[best_idx])
        best_entry = semantic_entries[best_idx]
        best_label = " / ".join(p for p in [best_entry["level1"], best_entry["level2"], best_entry["level3"]] if p)

        name = row.get("Funding Request Name", f"row {idx}")
        scores.append(best_score)
        print(f"{best_score:.3f}  {name}  -> best match: {best_label}")

    if not scores:
        print("\nNo General Population rows found to check.")
        return

    scores = np.array(scores)
    print(f"\n{rows_checked} General Population rows checked.")
    print(f"Score distribution: min={scores.min():.3f}  p25={np.percentile(scores,25):.3f}  "
          f"median={np.median(scores):.3f}  p75={np.percentile(scores,75):.3f}  max={scores.max():.3f}")
    print("\nLook at this spread before picking a threshold. If most scores cluster")
    print("tightly together regardless of whether the match looks right or wrong,")
    print("that's the anisotropy issue — a single fixed threshold may not separate")
    print("genuine matches from noise well, and the suggestion column may need a")
    print("higher bar, or a different scoring approach (e.g. centering embeddings,")
    print("or comparing against a 'null' baseline score) to be trustworthy.")

if __name__ == "__main__":
    main()