> **HANDOFF COPY.** This is the authoritative narrative record of everything DONE. Sections 1-12 cover the
> pre-spec pipeline (up to the 12-field consolidated-file spec, ~00:30 2026-10-30). **Section 13** covers the
> post-spec **accuracy-first pivot** (6-company pilot + LOCKED methodology + Step A/B page-cleaning +
> benchmark-numerator decision) — see also the dedicated doc `docs\POST_SPEC_PIVOT_accuracy_first.md`.
> All script paths are relative to this project folder: `scripts\_common\`, `scripts\<TrackFolder>\`, and
> `scripts\PostSpec_Pivot\` (the pivot). The next deliverable to build is in `docs\CONSOLIDATED_FILE_SPEC.md`.

# Jani Capsight — GCC Talent Mapping Pipeline (Track-1, Track-2, Track-2 Part-2)
_Last updated: 2026-10-28. This file is the authoritative record of how the Jani Capsight GCC talent-mapping
was built. Any Claude session or person reopening this project should read this first. All counts are as of
2026-10-28._

---

## 1. GOAL
For Capsight's company lists (Track-1, Track-2, and Track-2 Part-2), find the LinkedIn profiles of people who
**worked or currently work** at each company in India, matched by the company's **LinkedIn entity (slug)**,
then apply curation rules and report **ever-worked** and **currently-working** counts, with **per-city**
breakdowns for Part-2. The extracted profile data is the deliverable, plus summary Excels.

## 2. DATA SOURCE (STRICTLY READ-ONLY)
ziplabs passive_IN dump:
`C:\Users\LENOVO\Downloads\hiresense_data_ziplabs\ziplabs_passive_IN_20260827` + `...\ziplabs_passive_IN_20261012`
= 282 `.jsonl.gz` shards, ~97.6M India LinkedIn profiles. Read-only (see root CLAUDE.md PART 9/17). All outputs
are written ELSEWHERE (the Jani Capsight project folder). Never write into the Downloads dump.

## 3. CORE METHOD (why slug-based)
- Each profile has `experience[]` with `company.lnkd_uid` and `company.lnkd_url1/2`. The **slug** = the
  `/company/<slug>` segment (or `lnkd_uid`). We match a profile to a company by **exact slug**, NOT display
  name — this catches differently-named entities (e.g. "J.P. Morgan" people sit on the `jpmorganchase` page).
- Pipeline per track: **resolve** company names → candidate slugs from the supply → **assemble** the kept slug
  set → **pull** all profiles at those slugs (all 32 original columns) → **connection filter** → **finalize**
  (bake curation rules into the stored data) → **count** (ever / currently-working, per company / per entity).
- **"Currently working" = Jani's logic (v2), the DEFAULT:** a role counts as current if
  `duration.present` is true **OR** it has a `duration.start` and **no** `duration.end`.
  "normal" current = `duration.present` only. (Documented in root CLAUDE.md PART 10.3a.)

## 4. KEY FILE LOCATIONS
**Scripts**
- Track-1: `scripts\Track1_CompanyResolve\scripts\` + `final_slugs.csv`, `final_slugs_clean.csv`
- Track-2: `scripts\Track2_CompanyResolve\scripts\` + `final_slugs.csv`
- Track-2 Part-2: `scripts\Track2_Part2\scripts\` + `final_slugs.csv`, `part2_entity_review.csv`
- Shared engines: `scripts\_common\` →
  `jani_rules.py` (SINGLE SOURCE OF TRUTH for curation rules: GCC-keyword gate for EY/Deloitte, excluded
  companies, connection floors), `top_companies.py`, `company_entity_scan.py`, `revised_counts.py`,
  `entity_consolidate.py`, `filter_connections.py`, `finalize_extracted.py`, `merge_csv_into_extracted.py`
- Slug checks / discovery: `scripts\SlugCheck\scripts\` → `slug_check_dump.py`,
  `slug_current_variants.py` (ever/normal/Jani per slug), `slug_current_variants_shards.py`,
  `company_discover.py`, `company_discover_multi.py`, `kpmg_ey_discover.py`

**Profile datasets (under `C:\Shree\Shreekanth-Hiresense\Jani Capsight\`)**
- `Track1_BySlug_profiles\shards` (raw pull) · `\shards_min10conn` (≥10 conn, finalized) · `\shards_min20conn` (≥20 conn)
- `Track2_BySlug_profiles\shards` · `\shards_min10conn` · `\shards_min20conn`
- `Track2_Part2_profiles\shards`
- `_sidecars` under each (uid → matched slugs)

**Deliverable files (Jani Capsight\)**
- `Microsoft_current_conn20.csv` (30,047 Microsoft current, ≥20 conn)
- `DEShaw_both_conn10.csv` (D.E. Shaw both entities, ≥10)
- `Bosch_BGSW_India_conn10.csv` (Bosch BGSW + bosch-india, ≥10 — parked for a future track)
- `Track1_Track2_company_currently_working.csv` (per-company summary)
- `Company_CurrentlyWorking_with_entities.xlsx` (per-company + 3 entity cols)
- `Track2_Part2_India_GCC_by_city.xlsx` (Part-2: Company | India total | Currently working | currently-working city split | People removed)

## 5. PIPELINE STEPS (reproduce / continue)
1. **resolve_entities.py** — scan dump, match role `company.name` to each target (leading-token entity
   expansion), record per (target, slug): example name, domain, distinct-profile count → `*_entity_review.csv`.
   Resumable per shard. 12 workers.
2. **assemble_final_slugs.py** — per company keep the dominant slug + same-domain siblings + any slug with a
   meaningful count (>= max(10, 5% of dominant)); drop junk/no-slug → `final_slugs.csv`.
3. **pull_by_slug.py** — scan dump, keep every profile with a role at a confirmed slug → gzip shards of all 32
   original columns + sidecars. 14–15 workers. Resumable. Output under Jani Capsight.
4. **filter_connections.py** `TRACK=.. MIN=10/20 [SRC_SUB=..]` — rewrite shards keeping only
   `miniprofile_connections >= MIN`; blanks removed. Writes `shards_min<MIN>conn`.
5. **finalize_extracted.py** `TRACK=.. [SHARD_SUB=..]` — physically rewrite a shard set to keep a profile only
   if it still qualifies for ≥1 company under the full ruleset (slug in final_slugs; EY/Deloitte need GCC
   keyword). This "bakes the rules into the data." Multi-company people are never lost.
6. **Counting** — `top_companies.py` / `company_entity_scan.py` / `revised_counts.py` (`TRACK=..`,
   `SHARD_DIR`/`SHARD_SUB` env to point at the ≥10 or ≥20 set). They import `jani_rules.py` so the EY/Deloitte
   GCC-keyword gate and company exclusions are applied identically everywhere.

## 6. CURATION RULES (the heart of it)
**Connection filters:** tracks filtered to **≥10** then **≥20** connections. Microsoft/Google/Amazon require
**≥35** (applied at attribution in `revised_counts.py`). Blanks removed.

**Jani's currently-working logic (v2):** default "currently working" = `present` OR (start & no end). "normal"
= present only. Both reported.

**Big-4 (Track-1):**
- **KPMG** → only slug `kpmg-us`.
- **PwC** → only slug `pwc-ac-india` (all other PwC slugs removed from final_slugs).
- **EY** (`ernstandyoung`) & **Deloitte** (`deloitte*` pages) → count a profile only if its profile has a
  **GCC/offshore keyword** anywhere: `GDS, GBS, GSS, GDC, GCC, USI, KGS, SSC` + "Global Delivery/Business/
  Shared Services", "Global Capability/Delivery Centre/Center", "Shared Services Centre/Center", "Acceleration
  Centre/Center", "Global Operations", "Centre/Center of Excellence". Standalone "US" EXCLUDED (noisy typo).
  This gate lives in `jani_rules.py` (GATED_COMPANIES) and is applied at count time (a kept multi-company
  person can have a Deloitte role we don't credit unless keyword).

**Companies removed as mistakes (added to the list in error — like Sankalp):**
- **Sankalp Semiconductor** = the **hcltech** page (HCLTech acquired Sankalp; LinkedIn merged the pages, so
  "Sankalp" resolved to `hcltech`, dragging in all ~420k HCLTech people). Removed `hcltech` from final_slugs;
  **physically dropped the 285,544 hcltech-only profiles** from the ≥10 extracted set. The 87,272 who ALSO
  worked at a real Track-1 company were KEPT (counted under that real company; their hcltech role ignored).
- **Kyndryl** (GCC *enabler*, not a GCC) — removed `kyndryl`/`kyndryl-india` from Track-2 final_slugs;
  physically dropped 21,694 Kyndryl-only profiles; multi-company kept.
- Goldman trimmed to just `goldman-sachs` (dropped `gs10ksb`, `goldman-sachs---10000-women-initiative`,
  `goldman-sachs-group-inc-us`).

**Per-company location / sales gates (attribution gates in `revised_counts.py`):**
- **Amazon** → connections ≥35, location in Hyderabad/Bengaluru/Mumbai/Chennai/Delhi-NCR/Coimbatore/Pune
  (profile OR Amazon-role location), and **drop current domestic-sales roles**.
- **NTT Data Group** → **Visakhapatnam/Vizag only**.

**Known mislabeled pages (acquisition or single-stray-profile; flagged, kept unless told otherwise):**
Infinera → `nokia` (Nokia acquired Infinera); `atos` → `cms-infosystems`; `virtusa` → `westen-tou-business-
solution` (staffing vendor); Standard Chartered → `astrazeneca`; Deloitte → `citifinancial`. Cause: a page is
admitted on a weak name/domain match, then the slug-pull takes everyone on it.

## 7. TRACK-2 PART-2 (DOMESTIC NEGATION) — detail
**Input:** `Downloads\Track2_Part2_Domestic_L3_Negation_v2 (1).xlsx`, sheet "Company - L3s to negate",
cols `Company Name` | `L3s to negate`. 1,046 companies: 639 "none" (pure GCC, nothing to negate), 408 with a
semicolon list drawn from **24 distinct negate-L3 categories** (Field & Territory Sales, Sales Operations
domestic, Warehouse/Last-Mile, Plant QC/Production/Maintenance, Field Service, Channel/Distributor, Govt/PSU
Tender, Trade Marketing, Project Site, Modern Trade, Regulatory Liaison, Medical Device field, Pharma Field
Force, Retail Store, Hotel, Branch Banking, Dealership, Airline, Inspection, Facility Services, Agronomy,
Security Guarding).
**Engine:** `scripts\Track2_Part2\scripts\part2_negation.py`:
- ≥20 connections; interns/trainees excluded; India (dump is India).
- For each company a profile belongs to (by slug), REMOVE the person if their **job title(s) at that company**
  (v2 — title only, NOT headline/education; v1 matched headline and wrongly flagged e.g. "Attended IHM") match
  one of that company's negate categories — UNLESS protected.
- **PROTECT (never remove):** on a GCC-named entity slug (technology/global/capability/gbs/r&d/digital/shared
  services/gic/gcc/innovation/engineering|development centre) OR a title that is tech/R&D/software/analyst/
  data/finance/tax/EHS/brand/Revenue-Ops (bids/deal desk/sales enablement/incentive comp/pricing). ("consultant"
  was removed from protect in v2.)
- **City canon:** Delhi-NCR = Delhi+Gurugram/Gurgaon+Noida+Ghaziabad+Faridabad; Mumbai-MMR = Mumbai+Thane+Navi
  Mumbai; plus Bengaluru, Hyderabad, Chennai, Pune, Coimbatore, Kolkata, Ahmedabad, Visakhapatnam, etc.
- **small-N rule:** if a company's currently-working count < CUTOFF (=70, iterate per step 6), tag all to its
  largest city; else keep the city split.
- **EXCLUDED entirely:** IBM, HP, NTT (= Track-2 NTT Data Group, already done with Vizag), Bosch (full Bosch;
  the 2-entity BGSW+bosch-india is parked separately), People Tech; PLUS any company already in Track-1/Track-2
  final_slugs (5 overlaps: Merck & Co., Marelli, Lenovo, Arm Holdings, Elastic). Exclusion is dynamic
  (recomputed from the Track-1/2 final_slugs each run).
- **Per-company location limits:** Teleperformance = Hyderabad + Gurgaon; Siemens = Bengaluru/Chennai/Pune/
  Delhi-NCR; Philips = Bengaluru/Chennai/Delhi-NCR (matched on raw location tokens).
- **Output:** `Jani Capsight\Track2_Part2_India_GCC_by_city.xlsx` (Company | India total | Currently working |
  currently-working city split | People removed) + `_negation_samples.csv` (sample removals for QA).

## 8. FINAL NUMBERS (distinct people within each track; NOT de-duped across tracks) — 2026-10-28
### 8a. After MAX-3-ENTITIES-PER-COMPANY cap (current / latest)
Rule: each company capped to its top-3 LinkedIn pages by unique-profile count, rest removed (not archived);
EXCEPTIONS kept as-is (KPMG, PwC, EY, Deloitte, Goldman Sachs, Amazon, D.E. Shaw, PepsiCo, Mercedes, Bosch,
Teleperformance, Siemens, Philips, NTT Data Group). Script: `scripts\_common\apply_top3_cap.py` then
`finalize_extracted.py` + recount. final_slugs backed up to `final_slugs_precap_*.csv`.
| Track | Overall (ever / India) | Currently working (Jani) |
|---|---:|---:|
| Track-1 (≥20, capped) | 2,770,338 | 1,507,329 |
| Track-2 (≥20, capped) | 2,603,014 | 1,160,209 |
| Track-2 Part-2 (capped) | 1,184,276 | 477,175 |

### 8b. Before the cap (uncapped final_slugs)
| Track | Overall (ever / India) | Currently working (Jani) |
|---|---:|---:|
| Track-1 (≥20) | 2,797,023 | 1,517,960 |
| Track-2 (≥20) | 2,653,535 | 1,184,154 |
| Track-2 Part-2 | 1,237,980 | 498,767 |

Microsoft current (≥20): 30,047. D.E. Shaw (both entities, ≥10): 6,051 ever / 2,505 current. Bosch (BGSW+
bosch-india, ≥10): 51,858 ever / 23,212 current (parked).

## 9. GOTCHAS / LESSONS (so they aren't repeated)
- **Slug > name.** Always match by slug. Acquisitions merge LinkedIn pages → a small firm's slug can become the
  acquirer's (Sankalp=hcltech, Infinera=nokia). Watch for a tiny-company slug with a huge pulled count.
- **Views vs data.** Slug-level rules (KPMG/PwC/excludes) are baked into `final_slugs` + finalized shards.
  Per-profile rules (EY/Deloitte keyword, ≥35 conn, Amazon/NTT location, Part-2 negation) are necessarily
  applied at **count time** via `jani_rules.py`/`revised_counts.py`/`part2_negation.py`, because a kept
  multi-company profile still physically contains the other company's role.
- **Never delete multi-company people** — exclude a company by removing its slug/not crediting it, keeping the
  person for their other real companies.
- **Connections column** = `miniprofile_connections` (~8% blank; blanks treated as below-threshold → removed).
- **Performance:** one heavy scan at a time, ~10–15 workers; two parallel 15-worker scans lag the terminal.
- **Unicode:** print logs via UTF-8 (`sys.stdout.reconfigure(encoding='utf-8', errors='replace')`); some slugs
  contain non-cp1252 chars.
- **Discovery (`company_discover*.py`) scans the raw 97M dump** to find not-yet-pulled pages; normal counting
  uses the extracted `shards_min*conn` sets, never the raw dump (per user).

## 10a. CALIBRATION CHECK vs target (2026-10-28)
Script `scripts\_common\combined_current_by_city.py` — combined **currently-working (Jani)**, distinct by
uid across Track-1 + Track-2 + Part-2 (847 shards), all per-track gates applied → tallied by city/state and
compared to the user's "Calibrated Headcount" targets. Output `Jani Capsight\Calibration_match_city_state.csv`.
- **COMBINED currently-working distinct = 3,076,631 vs calibrated total 3,078,777 → 99.9% match (grand total).**
- Cities within ±20% (match): Pune 101%, Kolkata 103%, Coimbatore 99%, Ahmedabad 95%, Bengaluru 85%,
  Mumbai-MMR 82%, Kochi 81%. Under: Hyderabad 75%, Chennai 58%. Over: Delhi-NCR 132%, Trivandrum 168%,
  Jaipur 245%, Indore 252%, Nagpur 293%, Chandigarh 327%, Mysuru 618%.
- **559,649 profiles have an unparseable city** (unallocated) → pulls metros below 100%. Small cities read
  high because **profile city ≠ GCC work city** (people list hometowns while working remote/at a metro GCC);
  target counts by operating location.
- **L1/L2 sector tables not yet computed** — need a company→sector classification (from the user-provided
  canonical definitions); that's the next step.

## 10b. COMPANY COVERAGE + OPEN ITEMS (paused 2026-10-28, continue later)
Analyzed (resolved → in final_slugs): **Track-1 950/983, Track-2 593/595, Part-2 927/1,047** (~2,470 slots,
~2,460 distinct). **Not analyzed = 155** = 14 excluded-on-purpose + 141 "no LinkedIn page found" (name-match
miss). Full list → `Jani Capsight\NOT_analyzed_companies.csv` (track | company | reason).
- "No page found" ≠ absent: many exist under a differently-named slug (LSEG=`london-stock-exchange-group`,
  Pinterest India=`pinterest`, Dentsu, Mitsubishi UFJ, Databricks, Atlassian, CrowdStrike, DocuSign…) and can
  be added via URL like D.E. Shaw / Bosch. Part-2 "no page" are mostly GCC-named sub-entities (people on parent).

**TO DO when resuming:**
1. (Optional) Auto-discover LinkedIn pages for the 141 "no-page" companies and add the real ones.
2. **L1/L2 SECTOR classification** — map each company to its L2 industry / L1 sector using the user's
   canonical definitions (provided in chat 2026-10-28), then tally our **currently-working (Jani)** by sector
   and compare to the calibrated sector targets. (City/State calibration already done — 99.9% grand-total match.)

## 10. LOGS
- Root `master_log.txt` — milestone lines.
- Per-track `scripts\<Track>\workflow_log.txt` — full detail.
- This document is the narrative master record.

---

# 11. SESSION 2026-10-29 — function filter, location normalization, Samsung de-dup, coverage, Maruti
(Appended so a fresh session/account can resume. master_log.txt has the chronological milestones; this section is the narrative.)

## 11.0 HOW TO RESUME (read first)
- Read this file + root `master_log.txt` + root `CLAUDE.md`. All state is on disk (account-independent); do NOT rely on per-account memory.
- Live data: each track's `Jani Capsight\Track*_BySlug_profiles\shards_min20conn` (Track-2 has Samsung removed, 11.3). final_slugs per track in `scripts\Track*\...\final_slugs.csv`.
- Deliverable files all in `Jani Capsight\` (see 11.6). Word doc: `GCC_Pipeline_Documentation_withAppendix.docx` (has an appendix with the user's verbatim prompts).

## 11.1 STANDING RULE — 11-function filter = CURRENT only
The user's 11 functions: Accounting, Business Development, Consulting, Research, Engineering, Information Technology, Human Resources, Program and Project Management, Finance, Marketing, Product Management + Customer Service/Support (NOT domestic after-sales / sales-support). **The 11-function filter is applied to currently-working (Jani) only; OVERALL (ever-worked) is NEVER function-filtered.**

## 11.2 FUNCTION CLASSIFICATION — Capsight taxonomy (read the Excel directly)
- Source of truth = the user's Excel `C:\Users\LENOVO\Downloads\Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx` (669 L3 / 88 L2 / 12 L1; each L3 has Profile_Match_Regex). 9 regexes are double-escaped (`[\s\-/&.]`) — collapse `\`→`\` before compiling.
- `scripts\_common\gcc_taxonomy_classifier.py` — `load()` reads the Excel; `classify(headline,cur_title,skills,past_titles,summary,desc)` = title-regex first (longest match wins), else text; domestic→OUT_OF_SCOPE, unusable→NOISE. `map_to_user11(L1,L2)` maps to the 11 (BD has no in-scope family → ~0).
- `scripts\Track2_Part2\scripts\part2_function_filter.py` — Part-2 under the NEW rule.

## 11.3 TRACK-2 PART-2 — NEW RULE (replaced col-B negation with the 11-function filter)
Kept the other standing rules (EXCLUDE_P2 = IBM/HP/People Tech/NTT/Bosch + Track1/2 overlaps; LOC_ONLY Teleperformance=Hyd+Gurgaon, Siemens 4 cities, Philips 3 cities; drop interns; conn>=20). Dropped the column-B CAT negation; replaced by the 11-function keep (current only).
- **OVERALL ever-worked (no function filter): 1,256,998**
- **CURRENT (Jani) within the 11 functions: 332,174** (IT 153,594 / Eng 46,829 / ProdMgmt+CS 36,562 / HR 29,940 / Acct 18,847 / Mktg 18,363 / Fin 11,589 / PPM 10,048 / Consult 4,026 / Research 2,376 / BD 0).
- Files: `Track2_Part2_current_11functions.csv` (32 orig cols, 2.25GB) + `_by_company.csv` + `_by_entity.csv`.

## 11.3b SAMSUNG de-dup (keep Samsung only in Part-2)
Samsung was in BOTH Track-2 (company "samsung": samsung-electronics, samsungrndindiabangalore, samsungmobile) and Part-2 ("samsung electronics"). Per user: keep only in Part-2. Removed company "samsung" from Track-2 final_slugs (backup `final_slugs_presamsungremove_*.csv`) and physically removed samsung-ONLY profiles from Track2 shards_min20conn (`remove_samsung_track2.py`): 29,963 removed (45,052 samsung-only across all conns), 2,660,815 remain. "samsung e a" (samsung-engineering-india/samsungena) kept. **OPEN: 33 other Part-2 slugs still overlap Track-1/2 (honeywell, emerson, lenovo, bayer, merck, mitsubishielectric, arm, quest-global, safran, magna, nttdata, etc.) — fix via slug-based de-dup the same way if wanted.**

## 11.4 COMPANY COVERAGE AUDIT
`scripts\_common\coverage_audit.py` (reproducible from input Excels vs entity_review). Did-NOT-match (no LinkedIn page): Track-1 17/984, Track-2 2/596, Part-2 116/1047 = 135 total (+4 Part-2 excluded). File `Track_Company_Coverage_NotMatched.xlsx` (Summary + All_NotMatched + per-track sheets).

## 11.5 COMPANY-WISE LOCATION NORMALIZATION
`scripts\_common\location_normalize.py` over all 3 tracks' currently-working (Track-1/Track-2 = Jani + gates, no function filter; Part-2 = Jani + the 11-function keep). canon_city groups to metros (delhi ncr, mumbai mmr, bengaluru, pune, ...).
- Primary location = TIERED cap by company current headcount: **>5000 → city share >=2%; 1000-5000 → >=4%; <1000 → >=5%** (and >=10 profiles).
- Direct-tag (own city primary) → Reassign (current-role location = High, past-role = Low) → Exclude (no evidence). Reconcile direct+reassigned+excluded = total/company.
- Result (tiered): records 3,001,300 = tagged 2,268,992 + reassigned 361,358 + excluded 370,950. Final tagged 2,630,350. (Flat-5% earlier gave 2,550,813 / excluded 450,487.)
- Files: `Company_Location_Normalized.xlsx/.csv` (Company|Location|Original|Reassigned|Final|Excluded|Confidence) + `Company_Location_Normalized_profiles.csv` (uid,track,company,final_location,confidence,status). Cache `_locnorm_cache.csv.gz` (set env REBUILD=1 to re-scan; otherwise threshold tweaks are instant).
- **OPEN: user to review counts, THEN apply final_location into the profile CSVs (32 orig cols + final_location, excluded rows dropped) — per-track or combined, NEW files, not overwriting shards.**

## 11.6 MARUTI SUZUKI (standalone, not in any track)
4 pages: maruti-udyog-limited, maruti-suzuki-innovation, suzuki-research-and-development-center-india, suzuki-digital-private-limited. 3 areas: Greater Delhi / Greater Bengaluru / Pune-PCMC (metro-grouped). Overall ever (3 areas) 24,431; current Jani (3 areas) 9,302; current within 11 functions 4,513. Files `MarutiSuzuki_overall_3areas.csv`, `MarutiSuzuki_current_3areas.csv`, `MarutiSuzuki_final_11functions.csv`. Scripts in `scripts\MarutiSuzuki_Current\scripts\`.

## 11.7 CURRENT ALL-TRACK NUMBERS
Track-1 (capped): ever 2,770,338 / current Jani 1,507,329 (no function filter). Track-2 (capped, Samsung removed): ever ~2,603,014 / current ~1,160,209 (no function filter). Part-2 (new rule): ever 1,256,998 / current-in-11 332,174. NOTE: 11-function filter applied to Part-2 + Maruti only; T1/T2 current are full Jani. OPEN: decide whether to apply the 11-function filter to T1/T2 too.

## 11.8 RELEVANT SCRIPTS = 49 (see master_log + section 13 of the Word doc). Drop list: track1_extract, track1_current_counts, jpmc_current_breakdown (superseded/view); export_samsung_ericsson_nokia (test); maruti_probe, maruti_l3_breakdown (exploration); function_classifier (early hand-built, replaced by gcc_taxonomy_classifier). GitHub: NOTHING pushed; a consolidated folder was only proposed, not created.

## 11.9 DOCUMENTATION
Word doc for humans: `GCC_Pipeline_Documentation_withAppendix.docx` (15 sections + Appendix with the user's verbatim prompts). Generator: scratchpad `build_doc.js` (docx-js). An older `GCC_Pipeline_Documentation.docx` (no appendix) may be locked open in Word; consolidate to the single name once closed.

## 11.10 MISSED COMPANIES RECOVERY (2026-10-29)
The 135 not-matched companies (9.4 / coverage audit) were given LinkedIn URLs by the user in
Downloads\Track_Company_Coverage_NotMatched.xlsx (All_NotMatched sheet: col A track, B company, C URL, D+ extra
entity URLs). Pulled by those slugs ONLY (no discovery/expansion), >=20 conn, dedup. Part-2 missed companies get
intern-drop + the 11-function filter on CURRENT; Track-1/Track-2 plain. NO per-company special gates (none are
Amazon/Deloitte/EY/KPMG/PwC/MS/Google/NTT/Teleperformance/Siemens/Philips). Script
scripts\MissedCompanies\scripts\missed_companies_pull.py -> Recovered_{track1,track2,part2}_profiles.csv
(32 orig cols, ever-worked, dedup) + Recovered_companies_counts.csv (ever / current-Jani / current-in-11). 8
Part-2 companies had no URL -> still unmatched.

## 11.11 MERGED consolidated-location + calibration (2026-10-29)
location_normalize_all.py now ALSO runs the calibration (city/state/L1/L2 vs Calibration_targets.csv) from the
same single scan (no extra pass), with TODAY's logic (Part-2 11-function replacing negation; Samsung removed).
Tiered cap >5k=2%/1k-5k=4%/<1k=5% (>=10). Outputs: AllTracks_profiles_location_tagged.csv (one row per person,
ever-worked, 32 cols + final_location, excluded dropped), Calibration_match_ALL_updated.csv, and
company_sector_map_used.csv (Track-1 sectors from its input Excel; Track-2/Part-2 keyword-classified = APPROX,
review before trusting L1/L2 numbers). Targets persisted in Calibration_targets.csv (L1/L2/city/state).
Human doc: GCC_Pipeline_Documentation_withAppendix.docx (15 sections + appendix of the user's verbatim prompts).

## 11.10a MISSED pull — performance note (2026-10-29)
First attempt put the 674-rule taxonomy classify INLINE in the full-dump scan -> far too slow on the 2.6GB
shards (Part-2 missed companies are big: Raytheon, DHL, Logitech, Otis, element14...). Fix: PLAIN pull by the
given slugs only (>=20 conn, dedup), and compute the Part-2 11-function count AFTERWARD on the small recovered
Part-2 set (Recovered_part2_profiles.csv) rather than per-line during the dump scan. Same result, far faster.
General rule: never run the 674-regex taxonomy classify per-line inside a full-dump scan; classify the already-
extracted (small) result set instead.


# 12. SESSION 2026-10-30 — 5-PART DATASET VALIDATION & CORRECTION (industry from GCC master, centre mapping, reconciliation)

User brief: validate & correct the whole dataset (Track-1 + Track-2 + Part-2). Do NOT use the ziplabs companies
dataset for industry; use the GCC master list (Downloads\gcc master list (2).xlsx) as the reliable source.
Keep Delhi-NCR grouped. Flag unresolved companies rather than guessing. Targets are MINIMUM benchmarks.
Order: (1) company master -> (2) industry mapping -> (3) centre mapping -> (4) location+target reconciliation -> (5) QA.

## 12.1 STEP 1 — unique company master
Script scripts\_common\build_company_master.py. Dedup across the 3 tracks' final_slugs + recovered
(NotMatched(2).xlsx), union-find merge by normalized name OR shared slug. -> Company_Master_List.csv
(2,510 unique companies: company, aka_names, tracks, n_slugs, slugs, industry_L1/L2, L1_source, status).

## 12.2 STEP 2 — industry from the GCC MASTER (validated), with the slug-collision fix
Script scripts\_common\map_industry_from_gcc_master.py. Reads gcc master list (2).xlsx (hdr row idx 3; cols
Company Name / LinkedIn Entity URL(s) / L1 Sector / L2 Business Model Industry + entity names). GCC-master L1
names == our target L1 names EXACTLY (13/13) and L2 EXACTLY (26/26) -> join needs NO remapping.
  BUG FOUND & FIXED: first pass matched SLUG-first, and polluted/colliding slug lists produced wrong hits —
  Amazon->Howmet Aerospace (Industrial), HPE->United Parcel Service (Logistics), EY->Elevance Health (Healthcare),
  Deloitte mis-hit. FIX: match NAME-first (company + aka_names), slug only as fallback. Re-verified big names:
  Amazon/HPE/Google/Microsoft/Oracle=Software & Internet, IBM=Consulting, JPMorgan/EY/Deloitte=BFSI,
  Cisco=Telecom & Media, Pfizer=Healthcare. Result: 2,277 validated (2,214 name, 63 slug); 195 NEEDS_REVIEW
  (not in GCC master) — FLAGGED, never guessed. Outputs: Company_Master_List_industry.csv, gcc_master_clean.csv.
  The 195 are in Downloads\Companies_Needing_Industry_Review.csv WITH LinkedIn URLs (user asked for URLs not slugs).

## 12.3 STEP 3 — company -> centre mapping
Script scripts\_common\company_centre_mapping.py. Scans the pulled track shards (Track1/Track2 shards_min20conn
+ Part2 shards) + Recovered_*.csv; per profile slug->company, canon_city (Delhi-NCR grouped), tallies distinct
uids per (company,city) ever & current (Jani). Cross-refs the GCC master's per-city headcount columns to mark
CONFIRMED centres (city present in the master) vs PROFILE-ONLY (city only in our data, flagged, >=10). After the
Step-2 fix, industries were re-attached (131 corrected). -> Company_Centre_Mapping.csv (company, industry_L1/L2,
total ever/current, n_centres, confirmed_centres, profile_only_centres(flag), centre_detail_city:ever(cur), evidence).

## 12.4 STEP 4 — location + target reconciliation (CORRECTED)
Script scripts\_common\step4_reconciliation.py — scans the pulled track shards ONCE (850 inputs, 10 workers),
distinct current uids = 2,949,424. Fixes the old keyword-calibration's three faults:
  1. INDUSTRY from the validated GCC-master mapping (Company_Master_List_industry.csv), exact-name join — NOT the
     old keyword classifier.
  2. L1/L2 = DISTINCT uids per category (a person at two BFSI cos counts once). City/State also distinct-uid by own
     location. => no double-counting at any level.
  3. DELHI-NCR kept GROUPED: one city line vs combined Gurugram+Noida+Delhi target (330,854) and one state line
     "Delhi-NCR (grouped)"; old run triple-counted it (each sub-city showed the full 415,882 = 1039/508/199%).
     Now 420,787 = 127%.
  4. CITY coverage EXPANDED: 15 tier-2/3 targets canon_city had no alias for (Vadodara, Panaji & Goa, Udupi &
     Manipal, Aurangabad, Madurai, Vijayawada, Mangaluru, Lucknow, Shillong, Belagavi, Guwahati, Hubballi &
     Dharwad, Tumakuru, Shivamogga, Karwar) now map — all moved 0% -> real.
  5. Fixed Chandigarh state label -> "Punjab / Haryana / UT" (was showing 0%, actually 13,141 = 318%).
  -> Calibration_match_GCCmaster.csv (rows ordered L1, L2, STATE, CITY; ours_current_distinct, target_min, %, status).
  Over target (OK, minimums): BFSI 123%, Software 106%, Telecom 142%, Delhi-NCR 127%, most tier-2 cities.
  Shortfalls: L1 Logistics 50/Consulting 71/Healthcare 73/Automotive 80/Industrial 84/Retail 89%;
  City Chennai 54/Hyderabad 74/Mumbai 79/Bengaluru 81%; State Tamil Nadu 57% (biggest real gap).
  16.0% (472,008) current uids have an own-city outside the 34 benchmark cities (expected, not a gap).

## 12.5 STEP 5 — QA (Step5_QA_summary.txt)
Key finding: the industry shortfalls are largely a CLASSIFICATION gap, not a sourcing gap. The 195 unclassified
companies hold 231,157 current profiles (5.2%) and cluster in the exact short sectors:
Maersk(13,130)+DHL(3,303)->Logistics; EXL(24,914)+Teleperformance(24,495)+Virtusa(19,342)+CGI(19,095)+Randstad
->Consulting; Target(8,125)->Retail; AGS Health->Healthcare. Classifying them lifts those L1s directly. Plus the
Part-2 11-function restriction intentionally depresses Consulting/Healthcare/Industrial. The one genuine SOURCING
gap after accounting for those is Chennai / Tamil Nadu (54-57%) — likely under-coverage of Chennai GCCs
(auto/manufacturing/healthcare). Full corrections / gaps / unresolved / assumptions in Step5_QA_summary.txt.

## 12.6 OPEN ITEMS (await user)
- 195 unclassified companies -> Downloads\Companies_Needing_Industry_Review.csv (with LinkedIn URLs). Either user
  fills, or user approves mapping the obvious ones from reliable knowledge (then re-run step4_reconciliation.py).
- 19 still-missing companies (no working India URL / URL -> 0 profiles) -> Downloads\Still_Missing_Companies.xlsx
  (track noted). Await working URLs.

## 12.7 DELIVERABLES (Jani Capsight, copies of the last two in Downloads)
Company_Master_List.csv, Company_Master_List_industry.csv, gcc_master_clean.csv, Company_Centre_Mapping.csv,
Calibration_match_GCCmaster.csv (+Downloads), Step4_reconciliation_notes.txt, Step5_QA_summary.txt (+Downloads),
AllTracks_profiles_location_tagged.csv.gz (8.1GB, 4,861,064 distinct uids, everyone ever-worked, 32 cols+final_location).

## 12.8 NOTE on the superseded calibration
The earlier Calibration_match_ALL_updated.csv / company_sector_map_used.csv (section 11.11) used the keyword
classifier (APPROX) and triple-counted Delhi-NCR; they are SUPERSEDED by Calibration_match_GCCmaster.csv. Keep for
history only.


# 13. SESSION 2026-10-30 (after the spec) — ACCURACY-FIRST RECLASSIFICATION PIVOT
User pivot: BEFORE adding more companies or sourcing more profiles, improve profile-classification ACCURACY and
clearly separate classification error from real coverage gaps. This happened AFTER the 12-field spec and was
paused to build the handoff. Authoritative frozen rules: `reference\pivot_post-spec\GCC_Classification_Methodology_LOCK.md`;
full narrative: `docs\POST_SPEC_PIVOT_accuracy_first.md`; scripts: `scripts\PostSpec_Pivot\`; outputs:
`reference\pivot_post-spec\` (StepA_slug_reconciliation.csv, StepB_slug_decisions.csv, StepB_review_bucket.csv,
pilot_centre_coverage.csv, pilot_slug_validation.csv).

## 13.1 WHY (trigger)
The Step-4 calibration (12.4) counted people by their OWN profile city, producing metro shortfalls (Chennai 54%,
Hyderabad 74%, Tamil Nadu 57%). A 6-company pilot tested whether these were measurement artifacts or real gaps.

## 13.2 PILOT (6 companies: Std Chartered, Ford, Caterpillar, Zoho, Omega Healthcare, Target)
Script scripts\PostSpec_Pivot\pilot_centre_coverage.py. Mapping people to their actual WORKING location
(role location, not hometown — available for 64-73% of current profiles) flips the metro "gap" to overshoot:
Std Chartered Chennai 314%, Ford 165%, Caterpillar 202%. Also exposed: slug pollution (AstraZeneca merged under
Standard Chartered ~4,851 wrong; construction/retail under Target; construction-ai ambiguous under Caterpillar);
master imperfections (Omega all-Hyderabad in master but really Chennai/Trichy; Zoho Indian-HQ, benchmark meaningless);
and the master's LinkedIn-URL column being CORRUPT (Honeywell cell=decathlon-group etc.).

## 13.3 LOCKED METHODOLOGY (see the LOCK file for the full 8 rules)
(1) Currently working = Jani (overshoot over a minimum is fine). (2) Working location = role-loc -> profile-loc ->
UNLOCATED, Delhi-NCR grouped, centres-per-state separate (THIS is the fix that corrected the metro gap). (3) Company
identity = company-first on the master NAME; master LinkedIn-URL column NOT used (corrupt); pages come only from OUR
resolved slugs. (4) Ambiguous slug: >=60% keep / <20% drop / middle -> manual-review bucket with evidence. (5) Re-pull
from master URL = CANCELLED. (6) Per-dimension classification status = Correct / Needs Correction / Unverified +
source, dimensions independent, nothing forced. (7) Industry name-first from GCC master. (8) Function from Capsight
taxonomy native L1/L2.

## 13.4 BENCHMARK NUMERATOR (owner-confirmed: recommended action)
Count only foreign-captive GCCs. Exclude Indian-HQ firms (Zoho) and pure service-providers absent from the master
(EXL/Virtusa/Teleperformance/CGI) from benchmark totals, but KEEP them in the profile file FLAGGED (benchmark_eligible=No).

## 13.5 STEP A + STEP B (built)
Step A (stepA_slug_reconcile.py) -> StepA_slug_reconciliation.csv: our slugs matched to master company names.
Step B (stepB_page_clean.py) -> StepB_slug_decisions.csv (all 4,674 pages: keep/review + name_match_fraction +
real LinkedIn names) + StepB_review_bucket.csv (140 pages needing judgment). Buckets: 4,434 auto-keep / 140 review /
95 empty. The 140 are a MIX: mostly KEEP (acquisitions/renames/sub-brands: Vodafone->vois, NatWest->royal-bank-of-scotland,
Broadcom->symantec/vmware, Oracle->sun-microsystems), a minority DROP (Atos->cms-infosystems, Agilent->abc-consultants,
ArcelorMittal->essar-steel, AstraZeneca-under-StdChartered). The rule NEVER auto-drops these.
NOTE: a "~15.9M" figure in Step B = role-OCCURRENCES across pages, NOT people; real = ~4.86M distinct ever-worked /
~2.95M current.

## 13.6 PENDING (where to resume the pivot)
Adjudicate the 140 review-bucket pages (keep/drop + reason, owner sign-off) -> Step C rebuild the 12-field
consolidated master (CONSOLIDATED_FILE_SPEC.md) on the cleaned slug set with per-dimension status+source ->
Step D re-run city/state/industry/function reconciliation on WORKING location vs GCC-master minimums (Delhi-NCR
grouped, distinct-uid, foreign-captive numerator) + classification-error-vs-real-gap split.
