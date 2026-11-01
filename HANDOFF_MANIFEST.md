# HANDOFF MANIFEST — exactly what to send, with sizes

Total payload ≈ **22 GB**, delivered on a **pendrive** (this small package is sent separately as a zip). This
manifest lists the data files that were copied to the pendrive under `Jani Capsight\`; the recipient copies them
into `C:\Shree\Shreekanth-Hiresense\Jani Capsight\` on their machine (see `00_START_HERE.md` §7).

Legend: ✅ = included in the handoff. Everything is **pre-cutoff** (≤ the 12-field spec, ~00:30 2026-10-30).

---

## 1. THE FINAL FILE (your starting point)
| Size | File | Purpose |
|---:|---|---|
| 7.7 GB | `AllTracks_profiles_location_tagged.csv.gz` | ✅ 4,861,064 distinct people, 32 original cols + `final_location`. One row per uid. Build the 12-field file on top of this. |

## 2. RAW SUPPLY (the per-track pulls that produced the final file)
Only the **authoritative `≥20-conn` set** per track is sent (the raw `shards` and `shards_min10conn`
intermediates are left behind — reproduce-only).
| Size | Folder / File | Purpose |
|---:|---|---|
| 4.49 GB | `Track1_BySlug_profiles\shards_min20conn\` | ✅ Track-1 profiles, ≥20 conn, finalized |
| 65 MB | `Track1_BySlug_profiles\_sidecars\` | ✅ uid → matched-slug maps |
| 4.24 GB | `Track2_BySlug_profiles\shards_min20conn\` | ✅ Track-2 profiles (Samsung removed) |
| 57 MB | `Track2_BySlug_profiles\_sidecars\` | ✅ |
| 3.45 GB | `Track2_Part2_profiles\shards\` | ✅ Track-2 Part-2 profiles |
| 42 MB | `Track2_Part2_profiles\_sidecars\` | ✅ |
| 1.07 GB | `Big4_curated\` | ✅ EY/Deloitte/KPMG/PwC curated set |
| 352 MB | `Recovered_track1_profiles.csv` | ✅ "missing companies" recovered — Track-1 |
| 27 MB | `Recovered_track2_profiles.csv` | ✅ recovered — Track-2 |
| 915 MB | `Recovered_part2_profiles.csv` | ✅ recovered — Part-2 |
| 5 KB | `Recovered_companies_counts.csv` (in reference/) | ✅ per-company ever/current counts for the recovered set |
| 48 MB | `DEShaw_both_conn10.csv` | ✅ D.E. Shaw (both entities, conn≥10 — unique lower-threshold data) |

## 3. REFERENCE TABLES (small — used to standardize the 12 fields)
| Size | File | Purpose |
|---:|---|---|
| 0.4 MB | `Company_Master_List_industry.csv` | ✅ company → slugs, tracks, industry_L1/L2, status, matched_master — **the key join table** |
| 1.1 MB | `Company_Centre_Mapping.csv` | ✅ company → centre (city) mapping, Delhi-NCR grouped |
| 0.4 MB | `Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx` | ✅ function L1/L2 taxonomy (for `gcc_taxonomy_classifier.py`) |
| 1.1 MB | `gcc master list (2).xlsx` | ✅ the GCC master list (industry / HQ / per-city minimum targets). From `Downloads\`. |
| small | `Calibration_targets.csv`, `Calibration_match_GCCmaster.csv`, `Step4_reconciliation_notes.txt`, `Step5_QA_summary.txt`, `Track_Company_Coverage_NotMatched.xlsx`, `Recovered_companies_counts.csv` | ✅ reconciliation/benchmark results + coverage/recovery notes |

## 4. DOCS, LOGS, SCRIPTS (this package)
| Item | Purpose |
|---|---|
| `CLAUDE.md` | ✅ what a fresh Claude auto-reads to understand the folder |
| `00_START_HERE.md` | ✅ the human entry point — read first |
| `docs\Jani_Capsight_Documentation.md` / `.docx` | ✅ the MAIN readable documentation (plain-language: what/how/why) |
| `docs\JANI_GCC_PIPELINE_DOCUMENTATION.md` | ✅ detailed technical record (sections 1–12, trimmed at the cutoff) |
| `docs\POST_SPEC_PIVOT_accuracy_first.md` | ✅ the accuracy-first pivot after the spec (pilot + LOCK + Step A/B + numerator + pending) |
| `reference\pivot_post-spec\` | ✅ LOCK methodology + StepA/StepB CSVs + pilot CSVs (the pivot's data/outputs) |
| `scripts\PostSpec_Pivot\` | ✅ pilot_centre_coverage.py, stepA_slug_reconcile.py, stepB_page_clean.py (+ logs) |
| `chat_history\` | ✅ the Claude Code session transcript(s) + a README (background context) |
| `docs\DATA_STRUCTURE.md` | ✅ profile schema + the final file's 33 columns |
| `docs\JANI_CURRENTLY_WORKING_LOGIC.md` | ✅ the current-role definition (JANI, not normal) |
| `docs\CONSOLIDATED_FILE_SPEC.md` | ✅ the pending deliverable + field→source map |
| `logs\jani_master_log_through_cutoff.txt` | ✅ Jani milestones, trimmed at the cutoff (other projects stripped) |
| `logs\Track1/Track2/Track2_Part2_workflow_log.txt` | ✅ per-track detailed logs |
| `scripts\_common\` (23 scripts) | ✅ shared engines — curated to the Jani pipeline only |
| `scripts\<per-track folders>\` | ✅ resolve / pull / finalize / special-pull scripts |

## 5. DELIBERATELY NOT SENT (and why)
Only mandatory data + clean results are kept. Irrelevant / regenerable / superseded CSVs are left out to avoid
confusion and save space.
| Item | Why excluded |
|---|---|
| raw `ziplabs_passive_IN` dump | the licensed profile source — copied to the pendrive **separately** by the owner (too big for this package). Pull/discovery scripts need it; the next deliverable doesn't. |
| ziplabs `companies` dataset | **not used anywhere** in this project. |
| `Track2_Part2_current_11functions.csv` (2.1 GB) + `..._by_company/_by_entity`, `part2_in11_uids.txt`, `MarutiSuzuki_final_11functions.csv` | the 11-function *result* files — regenerable from the Part-2 supply + the scripts (`part2_function_filter.py` + the taxonomy). Logic kept, bulky outputs dropped. |
| `Company_Location_Normalized_profiles.csv` (211 MB) + `..._.csv`/`.xlsx` | per-uid location+confidence — regenerable via `location_normalize.py`; `final_location` is already in the final file. |
| `Microsoft_current_conn20.csv` (238 MB) | redundant — Microsoft is a Track-1 company, already in the Track-1 supply. |
| `Bosch_BGSW_India_conn10.csv` (360 MB) | a "parked" pull, not part of any track. |
| `Company_Master_List.csv`, `gcc_master_clean.csv`, `company_sector_map_used.csv`, `NOT_analyzed_companies.csv` | superseded / duplicate / intermediate — replaced by `Company_Master_List_industry.csv`, the GCC master xlsx, and the recovery. |
| `AllTracks_...withcompany.csv.gz` | was a truncated/corrupt half-finished file — deleted. |
| `FiveCompanies_overall_location.csv` | a throwaway 5-company test extract, not part of the pipeline. |
| the ~90 unrelated scripts in the shared `_common` folder | other projects (music, Verizon, US-demand, …) — would only confuse. |
| the post-spec pivot's heavy Step C/D *result* files | never produced (the pivot was paused before scaling) — the pivot's **inputs, logic and outputs ARE included** (see §4: `docs\POST_SPEC_PIVOT_accuracy_first.md`, `reference\pivot_post-spec\`, `scripts\PostSpec_Pivot\`); only the un-built bulky results are absent. |
| raw `shards` / `shards_min10conn` per track (~18 GB) | reproduce-only intermediates; the finalized `shards_min20conn` is sent instead. |
