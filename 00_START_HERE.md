# START HERE — Jani Capsight GCC Talent-Mapping handoff
_Packaged 2026-10-30. Read this file top to bottom before touching anything._

You are taking over a project that maps the India LinkedIn workforce of a large list of target companies
(GCCs), company by company, from a licensed LinkedIn profile dump. The data is already extracted and
de-duplicated; your next job is one well-defined deliverable (see §5).

---

## 1. CRITICAL RULES (break these and the numbers silently go wrong)
1. **"Currently working" = the JANI definition only** (`duration.present` True **OR** `start` set and **no**
   `end`). NOT the normal present-only definition. Full detail: `docs/JANI_CURRENTLY_WORKING_LOGIC.md`.
2. **Match profiles to companies by SLUG, never by display name** (`company.lnkd_uid` / `/company/<slug>`).
3. **Only the ziplabs `passive_IN` profiles dataset is used.** The ziplabs **`companies` dataset is NOT used
   anywhere** (resolution, pull, and industry all avoid it; industry comes from the GCC master list).
4. **Preserve all 32 original LinkedIn columns; never overwrite them.** Add standardized fields as new columns.
5. **Flag, don't force.** A profile/company that can't be classified confidently is marked for review, never
   given a wrong tag. Dimensions are independent — never drop a whole profile because one field is missing.
6. **Never delete a multi-company person** — drop the company's slug / don't credit it, keep the person.

## 2. WHAT'S IN SCOPE (the cutoff)
This handoff contains everything done **up to the consolidated-file spec (~00:30, 2026-10-30)** — the pipeline,
the per-track pulls, location normalization, the missing-company recovery, and the 5-part industry / centre /
reconciliation validation that produced the final file and the company master.

**ALSO INCLUDED:** the **accuracy-first reclassification** pivot — a 6-company pilot, a LOCKED methodology, and
a Step A/B slug page-cleaning pass — plus the benchmark-numerator decision. It was done after the spec but
before handoff, and was **paused** before the heavy Step C/D result files (never produced). It refines HOW the
next deliverable is built. Read it after the main docs:
`docs/POST_SPEC_PIVOT_accuracy_first.md` (narrative), `reference/pivot_post-spec/` (the LOCK + Step A/B CSVs),
`scripts/PostSpec_Pivot/` (the scripts). Key shifts it introduces: working-location mapping (role→profile),
"don't trust the GCC-master URL column — use the master NAME", foreign-captive-only benchmark numerator, and
per-dimension Correct/Needs-Correction/Unverified status.

## 3. CURRENT STATE — what is DONE
- All three tracks pulled, connection-filtered (≥20), curated, and finalized. See documentation §5–§8.
- Missing companies recovered; Maruti / Toyota / Walmart / D.E. Shaw / Bosch special pulls done.
- Location normalized → every profile has a `final_location` (canonical work-city, Delhi-NCR grouped).
- Company master built and industry-validated against the GCC master list; centre mapping + city/state/industry
  reconciliation vs the GCC-master minimum targets done (documentation §12).

### The final file (your starting point)
`AllTracks_profiles_location_tagged.csv.gz` — **8.1 GB, 4,861,064 distinct people** (one row per uid, everyone
ever-worked at a target company), **33 columns = 32 original + `final_location`.** It has NO `company` column
yet — adding the standardized fields is the pending deliverable. Full column list + field meanings:
`docs/DATA_STRUCTURE.md`.

> ⚠️ Note: the "~15.9M" figure some intermediate tables show is a role-occurrence tally, NOT people. The real
> headcount is **~4.86M distinct people** (≈2.95M currently-working by the Jani definition).

## 4. THE NUMBERS AT A GLANCE (distinct people within each track; documentation §8/§11.7)
| Track | Ever-worked | Currently-working (Jani) |
|---|---:|---:|
| Track-1 (≥20, capped) | 2,770,338 | 1,507,329 |
| Track-2 (≥20, capped, Samsung removed) | 2,603,014 | 1,160,209 |
| Track-2 Part-2 (ever) / (current in 11 functions) | 1,256,998 | 332,174 |
Combined currently-working distinct (city/state calibration) ≈ 3.08M (99.9% of the owner's calibrated total).

## 5. YOUR NEXT DELIVERABLE
Build the **one consolidated master profile file** with the 12 standardized fields, one row per uid, all
original columns preserved. Full spec + where every field comes from: **`docs/CONSOLIDATED_FILE_SPEC.md`.**
Build it on top of the final file above.

## 6. PERFORMANCE / HARDWARE (same laptop config — do not melt it)
- **One heavy scan at a time, 10–12 worker processes max** (12 = measured peak on this machine). Do NOT raise
  the worker count or run two multi-worker scans at once — it lags the whole terminal and spikes memory.
- **Stream the big `.gz` files line-by-line** (`gzip.open(path,'rt')` + `csv`), shard by shard. **Never load
  the 8 GB file into pandas** or read it all into memory.
- `experience` and other list columns are **Python-repr strings → parse with `ast.literal_eval`**, not json.
- Do **not** run the 674-regex taxonomy classifier inline inside a full-dump scan — classify the already-
  extracted (small) result set instead (documentation §11.10a).
- Print logs as UTF-8 (`sys.stdout.reconfigure(encoding='utf-8', errors='replace')`) — some names/slugs are
  non-cp1252.

## 7. FOLDER LAYOUT TO RECREATE (so the scripts' paths resolve)
The scripts use absolute Windows paths, now all self-contained under the project folder. On a machine
matching the original config, recreate:
- `C:\Shree\Shreekanth-Hiresense\Jani Capsight\` ← **everything**: the data files, the contents of
  `reference/`, and the `scripts/` folder (the scripts reference each other under
  `C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common\` — no separate "JD" workspace is needed).
- `C:\Users\LENOVO\Downloads\gcc master list (2).xlsx` and the two owner review CSVs.
- **If your Windows username is not `LENOVO`, or your drives differ, you must either recreate these paths or
  edit the hardcoded paths at the top of the scripts.** This is the #1 thing that will trip you up.
- The raw licensed `ziplabs_passive_IN` dump is **NOT included** (it's the purchased source). The pull /
  discovery scripts (`resolve_entities.py`, `pull_by_slug.py`) need it and can't be re-run without it — but
  your deliverable (the consolidated file) works entirely off the already-extracted files, so you don't need
  the raw dump.

## 8. WHAT'S IN THIS PACKAGE
```
CLAUDE.md                   <- what a fresh Claude auto-reads to understand this folder
00_START_HERE.md            <- you are here (human entry point)
HANDOFF_MANIFEST.md         <- every data file/folder that was copied to the pendrive, with sizes
docs/
  Jani_Capsight_Documentation.md/.docx <- the MAIN readable documentation (what/how/why, plain language)
  JANI_GCC_PIPELINE_DOCUMENTATION.md    <- detailed technical record (sections 1-12)
  DATA_STRUCTURE.md                     <- the profile schema + the final file's columns
  JANI_CURRENTLY_WORKING_LOGIC.md       <- the current-role definition (JANI, not normal)
  CONSOLIDATED_FILE_SPEC.md             <- the pending deliverable
logs/
  jani_master_log_through_cutoff.txt   <- Jani milestone log, trimmed at the cutoff
  Track1/Track2/Track2_Part2_workflow_log.txt
chat_history/               <- the Claude Code session transcript(s) (background context)
reference/                  <- small tables: company master, industry, taxonomy, GCC master, calibration
scripts/                    <- the Jani pipeline scripts only (curated; see §9)
```
The big data (the ~7.5 GB final file + the ~14 GB supply shards) is NOT inside this folder — it is delivered
**separately on a pendrive** (see the manifest). Place it under `C:\Shree\Shreekanth-Hiresense\Jani Capsight\`
per §7.

## 9. THE SCRIPTS THAT MATTER
`scripts/_common/` holds the shared engines; the per-track folders hold the resolve/pull/finalize scripts.
The ones you'll actually use for the next deliverable:
- `_common/jani_rules.py` — single source of truth for the curation rules (import from it).
- `_common/gcc_taxonomy_classifier.py` (+ `extract_gcc_taxonomy.py`) — function L1/L2 from title/headline.
- `_common/build_company_master.py`, `map_industry_from_gcc_master.py` — company master + industry.
- `_common/location_normalize.py` / `location_normalize_all.py` — how `final_location` was produced.
- `_common/step4_reconciliation.py`, `company_centre_mapping.py` — city/state/industry reconciliation.
- `_common/finalize_extracted.py`, `filter_connections.py`, `revised_counts.py`, `top_companies.py` — pull/count engine.
Per-track: `Track1_CompanyResolve/`, `Track2_CompanyResolve/`, `Track2_Part2/` (contains `part2_negation.py`,
imported by some `_common` scripts), plus `SlugCheck/`, `MissedCompanies/`, `MarutiSuzuki_Current/`,
`Toyota_India/`, `FiveCompanies/`, `WalmartGlobalTech_Slug/`.
Some per-track folders contain older/superseded variants (documentation §11.8 lists them) — the documentation
and `jani_rules.py` are authoritative if anything disagrees.

## 10. OPEN ITEMS (owner still owes input — don't block on them)
- **197 companies with unresolved industry** → `Downloads\Companies_Needing_Industry_Review.csv` (flagged, not guessed).
- **19 still-missing companies** (no working India URL) → `Downloads\Still_Missing_Companies.xlsx`.
