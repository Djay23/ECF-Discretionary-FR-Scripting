import sys
import re
import pandas as pd
from openpyxl import load_workbook

"""
ethnic_tagger.py

- Reads a taxonomy sheet and a funding requests sheet from the same .xlsx file
- For each row in the funding sheet, searches Purpose, Project Final Description
- and Project Summary Description for ethnic origin keywords defined in the taxonomy

Fills Ethnic 1, Ethnic 2, Ethnic 3 columns based on the deepest match found (this case needs to be revised per Bianca's input)

To Run:
    python ethnic_tagger.py "C:\Users\oadode\OneDrive - Edmonton Community Foundation\Desktop\Discretionary FR working Folder - Oreva\Discretionary FR Working - 2025 (Oreva).xlsx"

Configuration Variables:
    TAXONOMY__DEF_SHEET(ethnic origins)     - name of the sheet containing the taxonomy definitions
    DISCRETIONARY_FR_DATA                   - name of the sheet containing funding requests
    TAXONOMY__DEF_ENTRY1                    - column name for Level 1 in taxonomy definitions sheet
    TAXONOMY__DEF_ENTRY2                    - column name for Level 2 in taxonomy definitions sheet
    TAXONOMY__DEF_ENTRY3                    - column name for Level 3 in taxonomy definitions sheet
    INPUT_COLS                              - list of columns to search for keywords in funding requests sheet
    OUTPUT_ETHNIC1                          - output column for Level 1 match
    OUTPUT_ETHNIC2                          - output column for Level 2 match
    OUTPUT_ETHNIC3                          - output column for Level 3 match
    BIPOC_KEYWORDS                          - keywords that should map to Multiple Ethnic and Cultural Origins
"""

# -- Jargon Config. ---
TAXONOMY__DEF_SHEET = "Taxonomy - Definitions"
DATA_SHEET = "Discretionary Funding Requests"

TAXONOMY__DEF_ENTRY1 = "Ethnic and Cultural Origins Level 1"
TAXONOMY__DEF_ENTRY2 = "Ethnic and Cultural Origins Level 2"
TAXONOMY__DEF_ENTRY3 = "Ethnic and Cultural Origins Level 3"

# Input columns to read keywords from
INPUT_COLS = [
    "Funding Request Name",
    "Purpose",
    "Final_Project_Description",
    "Final_Summary_Description",
]

# Ouput columns to write ethnic group identified from Taxonomy definitions sheet
OUTPUT_ETHNIC_1 = "Ethnic 1 - FR"
OUTPUT_ETHNIC_2 = "Ethnic 2 - FR"
OUTPUT_ETHNIC_3 = "Ethnic 3 - FR"

# Keywords to look for (automatically mapped for other origin keywords)
BIPOC_KEYWORDS = [
    "bipoc",
    "qtbipoc",
    "people of color",
    "black african",
    "poc",
    "racialized", # what about 'marginalized'?
    "marginalized",
    "grassroots", # what about 'Ethnocultural'. Some examples list 'grassroots' and 'indigenous' but only refer to indigenous ethnic group : "grassroots organizers" line 329
]

# TODO
"""
Read Column D in taxonomy definitions sheet to build a mapping of keywords 
using the word 'Origins' as a delimiter to determine the level of the keyword (L1, L2, L3).
For example, if the cell contains "African Origins Southern and East African Origins Ugandan", 
we would extract: 
- L1: African
- L2: Southern and East African
- L3: Ugandan
"""

def clean(text):
    """Lowercase and strip a string, return empty string if not a string or if NaN"""
    if pd.isna(text) or not isinstance(text, str):
        return ""
    return text.strip().lower()


#-- Taxonomy Definitions Sheet Processing --
def build_taxonomy(tax_df):
    """
    Build a list of taxonomy entries sorted by depth (deepest first)
    Each entry is a dict: {keyword, level1, level2, level3, depth}
    Depth 3 = Entry 1 + Entry 2 + Entry 3 all present
    Depth 2 = Entry 1 + Entry 2 present, Entry 3 empty
    Depth 1 = Entry 1 only
    """
    
    def clean(val):
            if not val:
                return ""
            val = str(val).lower().strip()
            val = val.replace("origins", "")
            return val.strip()

    entries = []

    for _, row in tax_df.iterrows():
        e1 = clean(row.get(TAXONOMY__DEF_ENTRY1, ""))
        e2 = clean(row.get(TAXONOMY__DEF_ENTRY2, ""))
        e3 = clean(row.get(TAXONOMY__DEF_ENTRY3, ""))

        if not e1:
            continue  # Skip empty rows

        if e3:
            depth = 3
            keyword = e3
        elif e2:
            depth = 2
            keyword = e2
        else:
            depth = 1
            keyword = e1
        
        # Needs to be changed later because column follows a conditional format (Specific origin in level can only be selected if its corresponding level 1 & 2 are selected)
        entries.append({
            "keyword": keyword,
            "keywords": list(filter(None, [e1, e2, e3])),
            "level1":  row.get(TAXONOMY__DEF_ENTRY1, ""),
            "level2":  row.get(TAXONOMY__DEF_ENTRY2, ""),
            "level3":  row.get(TAXONOMY__DEF_ENTRY3, ""),
            "depth":   depth,
        })

    # Sort longest first so we favour longer matches (Eg. 'African' should not match 'Southern and East African Origins' OR 'Southern African' should match before 'African')
    entries.sort(key=lambda x: (-x["depth"], -len(x["keyword"])))
    return entries

#-- Discretionary Funding Requests Sheet Processing --
def get_search_text(row):
    """Combine all input columns into one lowercase search string"""
    pass

def main():
    pass

if __name__ == "__main__":
    main()
