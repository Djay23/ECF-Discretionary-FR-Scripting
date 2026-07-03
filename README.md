# Purpose:
Create an automation for a spreadsheet of funding requests, filling out the 'Ethnic' Sectors based on specified keywords pulled from 'Taxonomy-Definitions.xlsx'

-----------------------------

## Currently
- Configuration of Taxonomy definitions book and ethnic & cultural Origins sheet
- Configuration of Discretionary reports excel book
- Configuration of output to ethnic columns in FR sheet
- Taxonomy mapping created for keywords from 'Taxonomy - Definitions.xlsx'
- Ranking system based on longer matches favoured first (eg. 'Southern African' matches before 'African')
- Ranking and tie breaking system implemented to now 'accurately' map the correct ethnic groups to funding requests.

#### TO DO:
- Fix mapping net to handle cases discussed by rob & Bianca. More flagging
- More descriptive language for flagging
- Flag BIPOC --> Some 'BIPOC' Language might be used loosely, as well as: Marginalized, multicultural, grassroots, etc.

### Some changes:
- Black Canadian/African Canadian --> Other, Black
- Flag:
    - Ethnocultural, Multicultural, Racialized, Indigenous, Marginalized, grassroots
    Typically grouped within **Multiple Ethnic Groups**
- Black Francophones --> Other, Black
- Flag treaty 6, 7, 8. 
- If two groups are within the same general level 2, can be grouped in the same level 3: like Ukrainian & Eastern European mentioned. What about a case where it is 'Filipino' & 'West and Central Asian and Middle Eastern Origins', or 'Filipino' and 'Syrian'
    - Group with its most common sector if they have a sector level in common.
- African Canadian ignored and grouped with --> Other, Black (flag)??

-----------------------------

<!-- ## Cases to Handle:
- 'South African' should map to 'Southern and East African Origins'.
    - First check description concatenation for if any words from 'All Terms' column D appear. (eg. 'South African' is in description but not in Taxonomy Definitions excel, so how do we handle possible cases like these)
- How do we handle a country like Jamaica or trinidad who dont have a specific level 2 or 3 but are grouped in caribbean origins? -->

1. Look for known terms by level (deepest first)
2. If nothing matches then interpret phrase structure. (For eg. "this funding is for the south african children in elementary schools, teaching them to read and write.")

-----------------------------

## Case Breakdown (with examples)
### Case 1, Exact Match (Best Case):
    Example:
    - "Somali youth"
    - "Punjabi community"
    - "Cree families"

### Case 2, Level 2 Match (Subregion):
    Example:
    - "East African Students"
    - "South Asian Population"
    
### Case 3, Level 1 Match (Broad category):
    Example:
    - "African Communities"
    - "Asian Families"

### Case 4, Structured Phrase (Modifier + Children)
    Example:
    - "South African"
    - "West African"
    - "North African"
        This is for cases where it is not in taxonomy but follows a predictable pattern

### Case 5, Country/Nationality exists in taxonomy:
    Example:
    - "Kenyan"
    - "Ethiopian"
    - "Haitian"

### Case 6, Country/Nationality NOT in taxonomy:
    Example:
    - "Jamaican"
    - "Trinidadian"
    - "Brazilian"

### Case 7, Country Name instead of Nationality:
    Example: 
    - "People from Jamaica"
    - "Youth from India"

### Case 8, Multiple Groups:
    Example:
    - "African and Caribbean youth"
    - "Somali and Ethiopian Families"
    -  "As families from increasingly diverse cultural backgrounds turn to BCW for support beyond its original focus on Black communities"
    *How do we handle cases like this where it mentions a specific ethnic group but is actually targetting a more diverse and broader population?

### Case 9, BIPOC and Another group mentioned":
    Example:
    - "BIPOC and Asian" 
    *Anything that includes 'BIPOC' and another ethnic group is automatically BIPOC
    * This might not be the best way to handle this case because of examples like this:
    "This project will foster long-term community impact by building sustainable creative practices, supporting emerging Asian Canadian artists, advancing equity in technical stagecraft", but BIPOC is also mentioned in the project purpose and Summary description: "To develop a new performance fostering BIPOC visibility, mentorship, and cultural understanding"

### Case 9, Broad Identity Labels:
    Example:
    - "Black youth"
    - "Arab communities"
    - "Jewish population"

### Case 10, Bent Arrow mention:
    Example:
    - "Bent Arrow Traditional Medicine"
    This corresponds with 'North American Indigenous Origins'
    *TO NOTE: This is often in the Account name, and needs to be the final point of lookup --If the current conclusion falls under 'General Population'
    - 'Treaty 6' as indigenous

### Case 11, Grassroots:
    - Grassroots can be assembled for environmental or ethnic reasons. (These are two different sectors).
    - When grassroots exists in our data bank, look for other ethnic keywords, this will indicate ethnic origin. Else, is general.

### Case 12, General/No Specific Group:
    Example:
    - "All communities"
    - "Open to everyone"
    - OR None of the other cases satisfied, then only then group in General

<!--
### Solution:
- Convert rows into hierarchical tree (dictionary) (breadth first search)
    - Level 1 terms: African, Asian, Carribean, European, etc.
    - Level 2 terms: East African, West African, etc.
    - Level 3 terms: Nigerian, Somali, Ethopian
-->

<!-- ## Workflow:
- Loop through 'Taxonomy - Defintions.xlsx' and create future accessible mapping of Taxonomy definitions using column D 'All Items'. 
- Once mapping has been created, Concactenate columns "Final_Project_Description" + "Final_Summary_Description" + "Purpose" + "Funding Request Name" before beginning keyword search. 
    - Priority Listing:
        - Final Project Description & Final Summary Description
        - Purpose 
        - Funding Request Name
    *These are the orders we will search for keywords first (as a result there might not be a need for contactenation, and instead store as different indices in a list to loop through).
- Upon keyword search, go through case-by-case analysis and perform ranking to group ethnicities.
- After ethnicity grouping, go through manually to confirm accuracy, placing emphasis on "General Population" section. -->

## Classification Phrase Expansion:
> [!NOTE]
> Include the highlighting of what phrase was targetted in the Classification Flag Notes section.
> Need to Highlight Black Canadian Women for flagging.
- **Context Override**: 
    * Historical Reference Detected (including these phrases): 
        + Historically; Formerly; Previously; Originally; Used to serve (focus, target, support); Once (Served, Focused, Targeted, Supported); Founded; Established; Created; Was, Were, etc. 
    * Expansion Phrases (including these phrases): 
        + Expanding beyond; Expansion; Beyond its...; Regardless of ethnic background; Irrespective of..., etc.
    > **Note:** See code for more in-depth exploration of Historical Phrases.

- **Ambiguous**: 
    * Equity Term with no paired ethnic signal (including these phrases):
        + Marginalized, Grassroots, Ethnocultural, Racialized.
    * BIPOC mentioned alongside specific groups(s) [Ethnic Origin] (including these phrases):
        + Bipoc; QTBipoc; Bpoc; People of Colour; Black African + (Another Ethnic Origin). 
        <!-- needs to be expanded to include Level 2 & 3. `other_groups` currently only selects Level 1 -->

- **BIPOC Target Detected**:
    * Bipoc; QTBipoc; Bpoc; People of Colour; Black African.
    > **Note:** Include what indicators led to this classification.

> Implement Semantic similarity matching --> This will go through anything classified as General or other and take a closer look, acting as a tighter knit net for ethnic signals. 

> Layer 1:
    - Current model of looking at taxonomy definitions to match ethnic group.
> Layer 2:
    - Semantic Similarity Searching (Safety Net).
        - Nearest Neighbour Classification.
        - Confidence threshold and pick highest confidence match.
        - Tries to answer "What taxonomy entry is this text most semantically similar to?"


## Current Rule Engine Handles:
* Exact Matches
* Pattern Rules
* Country Mappings
* Negation
* Historical References
* Aspirational Language
* BIPOC Handling
* Organization lookup

*Layer 2 to handle when text contains implicit ethnic signals that aren't in keyword system.

## Current Flow:
* Run ethnic tagger script
* Loads Taxonomy - Definitions.xlsx
* Loads FR Testing.xlsx
* Build Taxonomy Entries
* Load Embedding Model
* Creates Vectors (Turns text into vectors: "Supporting Newcomers from the horn of africa --> )

> Flag anything that has Cultural Association 
> Black canadians as just black, african canadians should be classified as african origins
> Classification for refugee? -> General (we don't have classification for this)
> Ethnocultural, multicultural, refugee, immigrant without any ethnic signal is usually general, but we flag
> Flag francophone, immigrant, etc. 
> Afro-Caribbean - Should be classified as caribbean, was grouped with black, so should be black & caribbean which is multiple ethnic.
> "Kerala Cultural Association" --> India. Anything with cultural association should be flagged.

## To Note for EMbedding (ENGINE 2):
- Inspect the gap between the top two matches. we currently only look at the single best score: `best_idx = np.argmax[scores]`; to now: best_score >= threshold && (best_score - second_best_score) >= margin


## To run Files:
- Diagnose_semantic_scores.py:
    + python diagnose_semantic_scores.py "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\Taxonomy - Definitions.xlsx" "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\FR testing.xlsx"

- Ethnic_taggerv3.py:
    + python ethnic_taggerv3.py "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\Taxonomy - Definitions.xlsx" "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\FR testing.xlsx"



# Current course of action (2026-06-25)
### Review General Pop. CLassification:
Random sample of 50 General pop:
- Correctly General
- Missed Ethnic classification
- Population-specific but outside taxonomy
- Ambiguous even for a human

### Audit 64 'Ambiguous Equity Term' Rows
- How many should actually classify?
- If 50+ truly are General Population, leave the rule
- If it contains obvious ethnic signals, are we suppressing too aggressively?

### Audit 42 'Multiple Ethnic' rows
Look at:
- BIPOC + African
- BIPOC + Asian
- BIPOC + Caribbean
Is this something a human reviewer actually needs to look at?

# Sprints
## Sprint 1:
- Add plural normalization
- Generate diagnostic review workbook
- Review:
    - 50 General pop. rows
    - 64 Ambiguous Equity rows
    - 42 'Multiple Ethnic' rows
    
## Sprint 2:
- Use findings from real data to decide whether:
- Reference context rules are needed
- Additional oranization mappings are needed
- Semantic Engine thresholds need tuning


# 2026-06-30
- Continued auditing of script classification for correctness. 
## Sprint 1:
- 100 General pop. rows sample - Complete -> 100% accuracy
- 11 Ambiguous equity rows with no paired ethnic signal
- 55 'Multiple Ethnic' rows - Complete -> Case notes below.

> [!NOTES] 
> Include a flag that highlights words like "especially" or "particularly", "particularly for", etc. if used with an ethnic term. "BIPOC communities—particularly East African newcomers".
> Something like this should be grouped as African Origins not multiple ethnic "for African youth from diverse backgrounds including Kenyan, Ghanaian, Zimbabwean, Sierra Leonean, Somali, Ethiopian, Djiboutian, Namibian, Botswanan, Mozambican, South African, etc.". We only group as multiple ethnic if they have different level 1, or level 2 classifications. Otherwise if there is a common level 1 or level 2 classification, group in the respective category. For example: "Serving indian and Pakistani communities" Should be grouped under Asian Origins -> South Asian Origins, Not multiple origins.
> "Black African" should be grouped as African Origins, instead of: Other Ethnic and Cultural Origins -> Black, not otherwise specified. Previously had it under BIPOC.
> Have engine 2 look at our country mapping for possible country aliases? Like Namibia vs. Namibian.
> We can group the "BIPOC signal detected" flag as low priority as these were classified properly from our sample.
> How do we handle cases where it mentions african Canadian, and then later specifies Nigerian for example? Currently we view african canadian as black, so adding nigerian would group it as multiple ethnic with distinct groups present. We should group African Canadian as black unless there is a specificied African country mentioned or Africa as a region mentioned later, then we go with the grouping for the specified african country/region. Or should we just change the grouping of 'African Canadian' to African?
> Need to double check the flag: multiple sub-groups within same origin. if they are within the same origin, they should be classified under the same origin and not as multiple ethnic.
> french-speaking, francophone, french canadian should be treated as a language accomodation and not an ethnic group. Review 50 examples with "French", "French canadian", "francophone", "french-speaking" and if it is ambiguous/language accomodation or is actually a cultural/ethnic identity. French-speaking/Francophone can also be referring to African countries that speak french, like cameroon, or just anyone who speaks french. How should we handle this as this is different from European french people.
    Keep as ethnic signal:
    - French Canadian Association
    - Francophone Cultural Society
    - French heritage community
    - French cultural programming
### High priority flags (resulting in incorrect classification)
- Ambiguous: BIPOC mentioned alongside specific group(s)
> Need to fix how we handle "African Canadian", "Black Canadian", etc. right now if we get an example like: "Advancement of African Canadians", we first see 'African Canadians' which we collapse into 'Black -> Other Ethnic and Cultural Origins'. We then see the 'African' In 'African Canadians' and group that under African origins, so a sentence like "Advancement of African Canadians" gets grouped as Multiple ethnic origins and flagged as multiple distinct groups detected.
> Similar issue, if we see African Canadian, and then black later, it is treated as two distinct groups even though we currently have African Canadian to be black (this should probably change so African canadian is just african). 
> What about in cases where it says African Canadian and is for something like black History month, or something like 'for the advancement of black students in STEM'. How should we handle classification/flagging?
> Case where classified as multiple and flagged as distinct because Somali and Black mentioned. Should actually be classified as Somali. We need to flag when  we see anything with Black, and African/Caribbean origins because they could be using Black as the umbrella and then specify, or vice versa. For example: "Hate crimes targeting Black Muslims—especially young Somali Canadians" or "Somali project aims to strengthen cultural pride, foster inclusion, and create safe spaces for Black Muslim communities".
> Correctly grouped as multiple ethnic: "Our program services are available in multiple languages, including French, Somali, and Urdu", however based on the current proposed changes, this would have probably been flagged as languages and maybe incorrectly grouped. we can ignore an example like this as because these are languages corresponding to specific countries we can assume they are targetting multiple ethnic groups, especially after manually reviewing it.
> We need to flag when hindu is present because Hindu can imply indian, but not always. 
> Black and Indigenous should be classified as BIPOC. Currently treated as two different Ethnic categories when present together.
> Flag anything with "official-language minority" or "French" because it could be referring to the ethnic group or just the language. Tricky though because of this example: "It aims to increase the diversity of content on Wikimedia projects, improving the visibility of notable Canadian figures and underrepresented groups, including Indigenous communities, gender minorities, and official-language minority communities.";  "will engage approximately 120 participants, including the general public, students, educators, volunteers, and cultural organizations, in both French and English". Upon changing the classification of French, this would have been grouped as indigenous although it was for multiple ethnic groups.

# 2026-07-02
## Sprint 1 (Continued)
- 100 General pop. rows sample - Complete -> 100% Accuracy.
- 11 Ambiguous equity rows with no paired ethnic signal - Complete -> 100% Accuracy.
- 55 'Multiple Ethnic' rows - Complete -> Case notes Above.

- Hook up old pipeline to new refactored version.
- Compare new review report with previous pipeline version.
- Use python library for country matching instead of built out dictionary