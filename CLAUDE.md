# CLAUDE.md — read this first

You (Claude) have been opened on the **Jani Capsight — GCC Talent Mapping** handoff. This folder is a
**self-contained snapshot** of the project. Its core is the state at the **12-field consolidated-file spec**
(~00:30 2026-10-30); the later **accuracy-first pivot** (pilot + LOCK + Step A/B) is also included on top (see
the dedicated section below). Everything needed to understand what was done and to continue is in this folder.
Read, in order:
1. **`docs/Jani_Capsight_Documentation.md`** — the full plain-language narrative: what the project is, how the
   data was extracted, every rule/logic, and the results. (Also as `.docx` for humans.)
2. **`docs/CONSOLIDATED_FILE_SPEC.md`** — the next deliverable to build.
3. **`docs/DATA_STRUCTURE.md`** and **`docs/JANI_CURRENTLY_WORKING_LOGIC.md`** — the data schema and the
   current-role definition.
4. **`00_START_HERE.md`** — the same info oriented to a human owner, plus how to copy the data to this machine.
5. **`docs/POST_SPEC_PIVOT_accuracy_first.md`** — the accuracy-first reclassification work done AFTER the spec
   (the 6-company pilot, the LOCKED methodology, Step A/B page-cleaning, the benchmark-numerator decision) and
   what's still pending on it. Read it LAST — it refines how the next deliverable is built.

## SETUP — do this FIRST (the data is NOT in this folder; it arrives on a pendrive)
This zip has the docs, scripts, logs, chat history and small reference tables. **The actual data — the ~7.5 GB
final file and the ~14 GB Track-1/2/Part-2 + Recovered supply — is on a separate pendrive.** Before running
anything, set up the folder so the scripts' absolute paths resolve:
1. Create `C:\Shree\Shreekanth-Hiresense\Jani Capsight\` (if your Windows username isn't `LENOVO` or your
   drive differs, either recreate this exact path or edit the paths at the top of the scripts — see §7 of
   `00_START_HERE.md`; this is the #1 thing that trips people up).
2. From the **pendrive**, copy `Jani Capsight\*` (the final file + the Track/Recovered supply) into that folder.
3. From **this package**, copy `scripts\`, `reference\`, `docs\` into that same folder (so the engines land at
   `C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common\`).
4. (Only if you will re-pull from the raw dump) put the ziplabs `passive_IN` dump at
   `C:\Users\LENOVO\Downloads\hiresense_data_ziplabs\`. Not needed just to build the next deliverable.
5. Open Claude Code in `C:\Shree\Shreekanth-Hiresense\Jani Capsight\`. Now every path in the scripts/docs resolves.
You do NOT need the data to *understand* the project — only to run the pipeline or build the next file.

## What has been done (up to the cutoff)
- All three company lists (Track-1, Track-2, Track-2 Part-2) were resolved to LinkedIn pages and **all matching
  India profiles pulled** from the licensed `ziplabs passive_IN` dump, matched **by LinkedIn page slug**.
- Curation applied: ≥20-connection floor (≥35 for MS/Google/Amazon), KPMG/PwC page restrictions, EY/Deloitte
  GCC-keyword gate, per-company location gates, Sankalp/Kyndryl removals, Samsung kept only in Part-2.
- Each profile given a **working `final_location`** (role location → profile → unlocated; metros grouped,
  Delhi-NCR together).
- **Missing companies recovered** from client-supplied URLs (`Recovered_*` files).
- **Validated** against the GCC master: a de-duplicated company master (2,510 companies), industry classified
  by name (2,277 validated, 197 flagged), centre mapping, and reconciliation vs the master's minimum targets.
- Final output: **`AllTracks_profiles_location_tagged.csv.gz`** — **4,861,064 distinct people**, 32 original
  LinkedIn columns + `final_location`.

## The post-spec pivot (read after the main docs)
After the 12-field spec (and before the project was handed off), an **accuracy-first reclassification** pivot
was done: a 6-company pilot, a **LOCKED methodology**, a slug page-cleaning pass (Step A/B), and a
benchmark-numerator decision. It sits **on top of** the pre-spec pipeline (which is unchanged) and refines how
the next deliverable is built. Full account:
**`docs/POST_SPEC_PIVOT_accuracy_first.md`**; frozen rules: `reference/pivot_post-spec/GCC_Classification_Methodology_LOCK.md`;
scripts: `scripts/PostSpec_Pivot/`; outputs: `reference/pivot_post-spec/`. Key points a fresh Claude must know:
- **Working location** (role→profile→UNLOCATED) is the fix that showed the metro "shortfalls" were mostly a
  measurement artifact, not a real gap.
- The GCC master's **LinkedIn URL column is corrupt — do NOT use it**; anchor company identity on the master
  **NAME** and OUR resolved slugs. (The old "re-pull from master URL" idea is CANCELLED.)
- **Benchmark numerator = foreign-captive GCCs only**; Indian-HQ (e.g. Zoho) + service-providers (EXL/Virtusa/
  Teleperformance/CGI) are kept in the file but FLAGGED out of the benchmark.
- Classification status per dimension = **Correct / Needs Correction / Unverified** (+ source), independent.
- **Pending:** adjudicate the 140 review-bucket pages → Step C rebuild the 12-field master on cleaned slugs →
  Step D re-run the reconciliation on working-location. (The "15.9M" in Step B is role-occurrences, NOT people
  — real = ~4.86M people / ~2.95M current.)

## Non-negotiable rules (full detail in the docs)
- **"Currently working" = the JANI definition** (`duration.present` True **OR** start set and no end). NOT the
  normal present-only rule. Reuse `scripts/_common/jani_rules.py`.
- **Match people to companies by slug, never by display name.**
- **Only the ziplabs `passive_IN` profiles dataset is used.** The ziplabs `companies` dataset is used NOWHERE.
- **Preserve all 32 original LinkedIn columns; add new fields as new columns; flag, don't force; never drop a
  whole profile because one field is missing; never delete a multi-company person.**
- **Performance:** one heavy scan at a time, **10–12 worker processes max**; **stream the big `.gz` files
  shard-by-shard — never load the 8 GB file into pandas**; parse the `experience` column with
  `ast.literal_eval` (it is a Python-repr string, not JSON).

## Where things are (all self-contained under this project)
- `scripts/_common/` — shared engines (incl. `jani_rules.py`, `gcc_taxonomy_classifier.py`,
  `build_company_master.py`, `map_industry_from_gcc_master.py`, `location_normalize.py`,
  `step4_reconciliation.py`). Per-track folders hold each track's resolve/pull scripts + its `final_slugs.csv`.
  **Scripts reference each other by absolute path under `C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\`**
  — recreate that path (same machine config) or edit the path at the top of the scripts.
- `reference/` — the company master, industry, taxonomy, GCC master, calibration tables.
- `logs/` — milestone log (trimmed at the cutoff) + per-track detailed logs.
- `chat_history/` — the Claude Code session transcript(s) (background context; the docs above are the
  authoritative state).
- The **big data** (the ~7.5 GB final file + the ~14 GB supply shards) is NOT in this folder — it is delivered
  **separately on a pendrive**; see `HANDOFF_MANIFEST.md` and place it under
  `C:\Shree\Shreekanth-Hiresense\Jani Capsight\`. The raw ziplabs dump is also delivered separately (only
  pull/history scripts need it; the next deliverable does not).

## Open items (await the owner)
- 197 companies with unresolved industry (`Companies_Needing_Industry_Review.csv`).
- 19 companies still missing a working India LinkedIn URL (`Still_Missing_Companies.xlsx`).
- 140 page-cleaning review-bucket pages await keep/drop adjudication
  (`reference/pivot_post-spec/StepB_review_bucket.csv`) — the pivot was paused here.
