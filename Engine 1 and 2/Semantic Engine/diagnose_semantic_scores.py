import sys
import pandas as pd
import numpy as np
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

import ethnic_taggerv3 as et
import semantic_fallback as sf

from pathlib import Path 

# Claude Helper to help build strong confidence interval for accurate Semantic Matching.
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
print("Using ethnic_taggerv3 from:", et.__file__)
print("Using semantic_fallback from:", sf.__file__)

TOP_N = 20  # how many of the highest-scoring rows to print in full for manual review (after the overall score distribution stats)

def main():
    start_time = time.time()
    
    taxonomy_filepath = bootstrap.PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx"
    funding_filepath = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"

    tax_df = pd.read_excel(taxonomy_filepath, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_filepath, sheet_name=et.DATA_SHEET, dtype=str)

    taxonomy_entries = et.build_taxonomy(tax_df)
    scope_notes = sf.build_scope_note_map(
        tax_df, et.TAXONOMY_ENTRY1, et.TAXONOMY_SCOPE_NOTES, et.safe_display)
    semantic_entries, semantic_texts = sf.build_candidate_texts(taxonomy_entries, scope_notes)
    semantic_embeddings = sf.get_taxonomy_embeddings(semantic_texts)

    model = sf.get_model()

    results = []  # (score, name, best_label, combined_text, margin)
 
    for idx, row in data_df.iterrows():
        e1, e2, e3, flag = et.classify_row(row, taxonomy_entries)
        if e1 != et.GENERAL_POP:
            continue  # only General Population rows reach the semantic step in the real run
 
        combined_text = " ".join(t for t in et.get_column_texts(row) if t.strip())
        if not combined_text.strip():
            continue
 
        query_embedding = model.encode([combined_text], normalize_embeddings=True)[0]
        sim_scores = semantic_embeddings @ query_embedding

        best_idx = int(np.argmax(sim_scores))
        top_indices = np.argsort(sim_scores)[-3:][::-1]  # indices of the top 3 scores
        best_score = float(sim_scores[best_idx])

        # Handle margin check between best and second-best score
        sorted_scores = np.sort(sim_scores)
        second_best_score = float(sorted_scores[-2]) if len(sorted_scores) > 1 else -1.0

        margin = best_score - second_best_score

        best_entry = semantic_entries[best_idx]
        best_label = " / ".join(p for p in [best_entry["level1"], best_entry["level2"], best_entry["level3"]] if p)

        top_matches = []

        for i in top_indices:
            entry = semantic_entries[i]

            label = " / ".join(
                p for p in [
                    entry["level1"],
                    entry["level2"],
                    entry["level3"]
                ] if p
            )

            top_matches.append(
                (float(sim_scores[i]), label)
            )

        name = row.get("Funding Request Name", f"row {idx}")
        results.append((best_score, second_best_score, name, best_label, combined_text, margin, top_matches))
 
    if not results:
        print("\nNo General Population rows found to check.")
        return
    
    scores = np.array([r[0] for r in results])
    print(f"{len(results)} General Population rows checked.")
    print(f"Score distribution: min={scores.min():.3f}  p25={np.percentile(scores,25):.3f}  "
          f"median={np.median(scores):.3f}  p75={np.percentile(scores,75):.3f}  max={scores.max():.3f}")
 
    # --- Top N highest-scoring rows, shown in full so match quality can be judged ---
    results_sorted = sorted(results, key=lambda r: r[0], reverse=True)

    print(f"\n=== Top {min(TOP_N, len(results_sorted))} highest-scoring rows ===")
    print("Read each one and judge for yourself: does the suggested category actually")
    print("fit the text, or is the model just picking the least-irrelevant option?")
    print()

    for score, second_best_score, name, best_label, combined_text, margin, top_matches in results_sorted[:TOP_N]:
        preview = combined_text[:160] + ("..." if len(combined_text) > 160 else "")

        print(f"{score:.3f}  {name}")
        print(f" -> suggested: {best_label}")
        print(f" text: {preview}")
        print(f" margin: {margin:.3f}")
        print(" top matches:")
        for match_score, match_label in top_matches:
            print(f"    {match_score:.3f}  {match_label}")

        print()
    
    # Margin distribution summary
    margins = np.array([r[5] for r in results])

    print(f"Rows with margin < 0.02: {(margins < 0.02).sum()}")
    print(f"Rows with margin < 0.05: {(margins < 0.05).sum()}")
    print(f"Rows with margin < 0.10: {(margins < 0.10).sum()}")

    print(
        f"Margin distribution: "
        f"min={margins.min():.3f}  "
        f"p25={np.percentile(margins,25):.3f}  "
        f"median={np.median(margins):.3f}  "
        f"p75={np.percentile(margins,75):.3f}  "
        f"max={margins.max():.3f}"
    )

    elapsed = time.time() - start_time
    print(f"Diagnostic run completed in {elapsed:.1f} seconds.")

if __name__ == "__main__":
    main()