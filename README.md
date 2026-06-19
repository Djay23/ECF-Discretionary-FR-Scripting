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
- African Canadian ignored and grouped with --> Other, Black (flag)

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
- **Context Override**: 
    * Historical Reference Detected (including these phrases): 
        + Historically; Formerly; Previously; Originally; Used to serve (focus, target, support); Once (Served, Focused, Targeted, Supported); Founded; Established; Created; Was, Were
    * Expansion Phrases (including these phrases): 
        + Expanding beyond; Expansion; Beyond its...; Regardless of ethnic background; Irrespective of...



    