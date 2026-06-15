# Ethnic & Cultural Origins Classification – Detailed Implementation Handoff

## 1. Purpose

This document describes a deterministic, rule-based system for classifying free-text descriptions into the **Ethnic and Cultural Origins taxonomy**.

### Goals
- Convert unstructured text into structured taxonomy outputs
- Preserve as much specificity as possible
- Ensure results are consistent, explainable, and reproducible

### Constraints
- No machine learning (ML) or AI
- No external services (sensitive data)
- All outcomes must be driven by explicit rules or data

---

## 2. Problem Breakdown

### Input Characteristics
Text may contain:
- Exact taxonomy terms: "Somali", "Punjabi"
- Subregional descriptors: "East African"
- Derived phrases: "South African"
- Countries/nationalities: "Jamaican", "Brazilian"
- Broad identities: "Black", "Arab"
- Multiple groups: "Somali and Ethiopian"

### Output Requirement
Map input to:
- Level 1: Broad region
- Level 2: Subregion/group
- Level 3: Specific identity (if available)

---

## 3. System Architecture

The system is composed of five independent but sequential layers:

1. Text Normalization
2. Taxonomy Matching
3. Pattern Matching (Rules)
4. Country Detection + Mapping
5. Post-processing (multi-group, fallback)

---

## 4. Text Normalization

Before matching, standardize input:

- Convert to lowercase
- Remove punctuation
- Normalize whitespace

### Goal
Ensure consistent matching behavior

---

## 5. Taxonomy Matching (Primary Layer)

### Source
Column D ("All Terms")

### Key Idea
Each row contains a hierarchical path:

Level 1 → Level 2 → Level 3

Split into list:

Example:
"African Origins Southern and East African Origins Somali"
→ ["african", "southern and east african", "somali"]

### Rule
- Match deepest level first (L3 → L2 → L1)
- First match wins

### Output
Return matching hierarchy

---

## 6. Pattern Matching Layer

Handles structured phrases not explicitly in taxonomy.

### Example Patterns
- "south african"
- "west african"
- "north african"

### Concept
These follow a predictable format:

[direction] + [region]

### Mapping

| Pattern | Target Level 2 |
|--------|----------------|
| South African | Southern and East African |
| West African | Central and West African |
| North African | North African |

### Rule
- Apply only if no taxonomy match
- Map to existing Level 2 taxonomy term

---

## 7. Country Detection Layer

### Purpose
Detect entities not present in taxonomy

### Method
Use:

1. Lookup list (small, curated)
2. Optional normalization rules

### Example Detection List
- jamaica
- trinidad
- brazil
- india

### Normalization
Convert nationality → country:

- jamaican → jamaica
- brazilian → brazil

### Rule
If detected:
→ pass to mapping layer

---

## 8. Gap Mapping Layer

### Purpose
Map detected countries to taxonomy regions

### Example Mapping

- jamaica → caribbean
- trinidad → caribbean
- brazil → latin american

### Important
- Keep mapping minimal
- Only include gaps not covered by taxonomy

---

## 9. Region Depth Assignment

### Problem
Different regions have different max depths

### Solution
Define max depth per region:

| Region | Max Level |
|--------|-----------|
| African | 3 |
| Asian | 3 |
| Caribbean | 2 |
| Latin American | 2 |

### Rule
When mapping external entity:
→ assign deepest valid level

---

## 10. Multi-Group Detection

### Trigger
More than one group found

### Example
- "Somali and Ethiopian"
- "African and Caribbean"

### Output
"Multiple Ethnic and Cultural Origins"

---

## 11. Broad Identity Mapping

### Examples
- Black
- Arab
- Jewish

### Output
Map to:
"Other Ethnic and Cultural Origins"

---

## 12. Fallback

If no signals detected:

→ "General Population"

---

## 13. Complete Decision Flow

```
INPUT TEXT
   ↓
Normalize
   ↓
Exact Taxonomy Match?
   ↓ YES → return
   ↓ NO
Pattern Match?
   ↓ YES → L2
   ↓ NO
Country Detection?
   ↓ YES
   → Map to region
   → Assign level via depth rules
   ↓ NO
Multiple Groups?
   ↓ YES → Multiple Origins
   ↓ NO
Broad Identity?
   ↓ YES → Other Origins
   ↓ NO
Fallback → General Population
```

---

## 14. End-to-End Examples

### Example 1
"Somali youth program"
→ L3 match

### Example 2
"South African children"
→ Pattern → L2

### Example 3
"Jamaican youth"
→ Country → Caribbean
→ L2 assignment

### Example 4
"Somali and Ethiopian"
→ Multi-group → Multiple Origins

### Example 5
"Black youth programs"
→ Broad identity → Other Origins

---

## 15. What This System IS

- Deterministic classifier
- Rule-based engine
- Taxonomy-aligned mapper

---

## 16. What This System is NOT

- Not ML or AI
- Not NLP model
- Not self-learning

---

## 17. Maintenance Strategy

Only update when needed:

1. Add new country to lookup
2. Add mapping to region
3. Add pattern rule (if repeated case appears)

### Expected Size
- Country list: ~20–50 entries
- Mapping list: ~10–30 entries
- Pattern rules: <10 entries

---

## 18. Final Insight

The taxonomy defines structure.

The code ensures real-world language fits into that structure.



---

## 19. Advanced Edge Case Handling (CRITICAL ADDITION)

### 19.1 Context Override Layer (Highest Priority)

Problem: Mentions of groups ≠ actual target population.

Example:
"beyond its original focus on Black communities"

Rules:
- Detect phrases: 'beyond', 'expanding beyond', 'not limited to', 'formerly', 'historically', 'previously'
- If present, downgrade or ignore detected ethnic group

Output Rules:
- If expansion → Multiple OR General Population
- If historical reference → ignore earlier match

---

### 19.2 Example/Illustrative Mentions

Examples:
- "such as Somali or Ethiopian communities"
- "including Haitian populations"

Rules:
- Detect: 'such as', 'including', 'e.g.'
- Do NOT classify unless repeated elsewhere as true target

---

### 19.3 Multi-Group Conflict Resolution

If more than one valid group:
- Always return: Multiple Ethnic and Cultural Origins

Even if:
- Different levels (L1 + L3)
- Related groups (Somali + Ethiopian)

---

### 19.4 Nested Specificity

Example:
"East African communities like Somali youth"

Rule:
- Prefer deepest match (Level 3)
- If multiple L3 detected → Multiple

---

### 19.5 Ambiguity Handling

Examples:
- "Indian" (country vs Indigenous context)

Rule:
- Use nearby keywords for disambiguation
- If unclear → fallback to higher level or avoid classification

---

### 19.6 Overmatching Prevention

Example:
- "blacksmith program"

Rule:
- Use strict word boundaries
- Avoid substring matching

---

## 20. Enhanced Priority Order (FINAL)

1. Context Override (highest priority)
2. Multi-group detection
3. Level 3 matches
4. Level 2 matches
5. Pattern rules
6. Country mapping
7. Level 1 matches
8. Broad identity mapping
9. Fallback (General Population)

---

## 21. Failure Points Summary

Potential failure areas:
- Missing country mappings
- Misinterpreting contextual phrases
- Early stopping after shallow match
- Misclassification due to example mentions
- Ambiguous term handling
- Region depth inconsistency

Mitigation:
- Always scan entire text before classification
- Always apply priority hierarchy AFTER detection
- Maintain small, curated mappings

---

## 22. Expanded Edge Case Examples

| Input | Expected Output | Reason |
|------|----------------|-------|
| "beyond Black communities" | General / Multiple | Context override |
| "Somali and Ethiopian youth" | Multiple | Multi-group |
| "South African children" | Level 2 | Pattern rule |
| "Jamaican youth" | Level 2 | Country mapping |
| "Historically Somali communities" | General | Context override |
| "Programs such as Haitian groups" | No classification | Example mention |

---

## 23. Final System Philosophy

- Deterministic > Intelligent
- Structure-driven > Vocabulary-driven
- Context-aware > keyword-only matching

