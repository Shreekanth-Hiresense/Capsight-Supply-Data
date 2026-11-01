# THE PENDING DELIVERABLE — one consolidated master profile file

This is the **next thing to build**. It was specified by the project owner and is the agreed stopping point of
this handoff. Everything needed to build it is in this package.

## The requirement (owner's exact words)
> Along with all original columns, please ensure the final consolidated file includes the following
> standardized fields:
> - final_location
> - company
> - companies_all
> - industry_L1
> - industry_L2
> - function_L1
> - function_L2
> - matched_master_company
> - classification_status
> - classification_confidence
> - tracks
> - location_confidence
>
> Please preserve all original LinkedIn data and do not overwrite existing fields.
> The objective is to have one deduplicated master profile file where company, location, industry and
> functional classifications are standardized, validated and traceable.
> Any profiles that cannot be confidently classified should be flagged for review rather than assigned
> incorrect tags.

## Hard rules (do not break these)
1. **One row per person** (`uid`). The base file is already deduped to one row per uid.
2. **Preserve ALL 32 original LinkedIn columns.** Add the standardized fields as NEW columns; never overwrite
   an original field.
3. **Flag, don't force.** If a dimension can't be classified confidently, mark it for review — do not assign a
   wrong tag. Each classification dimension is independent: never drop a whole profile because one dimension is
   missing (e.g. a blank `final_location` must not remove the row).
4. Keep the **Jani** currently-working logic (see JANI_CURRENTLY_WORKING_LOGIC.md).

## Where each field comes from (all sources are in this package — recommended mapping, verify as you go)
Build on top of `AllTracks_profiles_location_tagged.csv.gz` (it already has the 32 original columns +
`final_location` + the `experience` column you need to derive company/function).

| Field | Source in this package |
|---|---|
| `final_location` | already present in the base file |
| `company` (current/latest target) + `companies_all` (full matched list) | derive from `experience[]`: resolve each role's slug (`company.lnkd_uid` / `lnkd_url1/2`) against the slug→company map in `reference/Company_Master_List_industry.csv` (its `slugs` column, pipe-separated). `company` = the company on the latest-start **current (Jani)** target role; `companies_all` = all matched target companies for that person. |
| `industry_L1`, `industry_L2`, `matched_master_company`, `tracks` | `reference/Company_Master_List_industry.csv`, joined by company (NAME-first). Industry in that file was validated against the GCC master list (not keywords, not the ziplabs companies dataset). |
| `classification_status` | the `status` column of `reference/Company_Master_List_industry.csv` → `validated` / `NEEDS_REVIEW` / `track1_excel_only`. (The NEEDS_REVIEW companies are listed with URLs in `Downloads\Companies_Needing_Industry_Review.csv` — an owner open item.) |
| `function_L1`, `function_L2` | the Capsight taxonomy classifier `scripts/_common/gcc_taxonomy_classifier.py` run on job title / headline / skills. Reads `reference/Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx`. Domestic → OUT_OF_SCOPE, unusable → NOISE. **Never run the 674-regex classify inline inside a full-dump scan** — classify the already-extracted set (documentation §11.10a). |
| `classification_confidence` / per-dimension status | record traceability per dimension; where evidence is insufficient, leave as review rather than forcing a value. |
| `location_confidence` | regenerate with `scripts/_common/location_normalize.py` — current-role location = `High`, past-role = `Low`. (The 211 MB per-uid `Company_Location_Normalized_profiles.csv` was not shipped to save space; it is reproducible from the supply + this script.) |

## Open items the owner still owes input on (don't block the build on these)
- **197 NEEDS_REVIEW companies** (industry unresolved) → `Downloads\Companies_Needing_Industry_Review.csv`
  (with LinkedIn URLs). Owner fills or approves mapping. These stay flagged, not guessed.
- **19 still-missing companies** (no working India URL) → `Downloads\Still_Missing_Companies.xlsx`. Await URLs.

> Note: the exact NEEDS_REVIEW count is whatever `Company_Master_List_industry.csv` actually contains today
> (the narrative mentions both 195 and 197 at different points — trust the file, not the prose).
