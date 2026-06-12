# Purpose:
Create an automation for a spreadsheet of funding requests, filling out the 'Ethnic' Sectors based on specified keywords pulled from 'Taxonomy-Definitions.xlsx'

-----------------------------

## Currently
- Configuration of Taxonomy definitions book and ethnic & cultural Origins sheet
- Configuration of Discretionary reports excel book
- Configuration of output to ethnic columns in FR sheet
- Taxonomy mapping created for keywords from 'Taxonomy - Definitions.xlsx'
- Ranking system based on longer matches favoured first (eg. 'Southern African' matches before 'African')

-----------------------------

<!-- ## Cases to Handle:
- 'South African' should map to 'Southern and East African Origins'.
    - First check description concatenation for if any words from 'All Terms' column D appear. (eg. 'South African' is in description but not in Taxonomy Definitions excel, so how do we handle possible cases like these)
- How do we handle a country like Jamaica or trinidad who dont have a specific level 2 or 3 but are grouped in caribbean origins? -->

-----------------------------

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

### Case 9, Broad Identity Labels:
    Example:
    - "Black youth"
    - "Arab communities"
    - "Jewish population"

### Case 10, General/No Specific Group:
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

## Workflow:
- Loop through 'Taxonomy - Defintions.xlsx' and create future accessible mapping of Taxonomy definitions using column D 'All Items'. 
- 
- 


    