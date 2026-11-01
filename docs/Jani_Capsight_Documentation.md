# Jani Capsight — GCC Talent Mapping: Full Documentation
_A complete, plain-language record of what was done, how the data was extracted, and every rule applied.
Written so that someone opening it for the first time can understand the whole project. Covers everything up
to 2026-10-30 (the point this project was handed over). Script paths are relative to this project folder
(`scripts\...`)._

---

## Contents
1. What this project is
2. The data we used
3. Key ideas you need first
4. How the people were extracted — the pipeline, step by step
5. Special rules for particular companies (and why)
6. The job-function filter (the 11 functions)
7. Location — where people actually work
8. Missing-company recovery
9. Validation & correction against the GCC master
10. The results (the numbers)
11. The final file
12. The scripts (where everything lives)
13. Key output files
14. Open items
15. The next deliverable
16. The accuracy-first pivot (after the spec)
- Appendix: key definitions & the original instructions

---

## 1. What this project is
CapSight maps the **India LinkedIn workforce of GCC companies** (Global Capability Centres). The client gave
three company lists — **Track-1**, **Track-2**, and **Track-2 Part-2**. For every company on those lists we
find the LinkedIn profiles of people who **work there now or worked there in the past, in India**, clean the
results with a set of rules, and report:
- **"ever-worked"** counts (anyone who had a role there at any time), and
- **"currently-working"** counts (people there right now, by our definition in §3),
with **per-city** breakdowns.

The deliverable is the **extracted profile data itself** plus summary tables and a validated company master.

## 2. The data we used
- **The profile source — "ziplabs passive_IN".** A licensed dump of ~**97.6 million India LinkedIn profiles**,
  one person per line, stored as compressed text files. It is **read-only** — we never change it, we only read
  it and write our results elsewhere. This is the **only** ziplabs dataset used.
- **NOT used:** the separate ziplabs "companies" dataset. (It was tried once for company matching, found noisy
  with empty domains, and abandoned. Company matching is done from the profiles themselves.)
- **The GCC master list** (`gcc master list (2).xlsx`): the client's reference of GCC companies with their
  industry, head-office, and **minimum expected headcount per city**. We use it to classify industry (by
  company NAME) and as the benchmark to compare our numbers against. Its numbers are **minimum** targets.
- **The Capsight function taxonomy** (`Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx`): the client's
  official list of job functions (12 top-level "L1" → 88 "L2" → 669 "L3"), used to classify what each person does.

## 3. Key ideas you need first
- **`uid` = a person's identity.** Each profile has a unique LinkedIn id; one row per person, no duplicates.
- **`experience[]` = a person's job history.** Each past/present role records the **company**, the **job
  title**, the **role location**, and the **dates** (start / end / "present").
- **We match a person to a company by the LinkedIn "slug" (page id), NOT by the company's written name.**
  Every company has a LinkedIn page with an address like `linkedin.com/company/<slug>`. Matching by slug
  catches people whose role is written differently (e.g. "J.P. Morgan" people sit on the `jpmorganchase` page).
  ⚠️ When a big company acquires a small one, LinkedIn often merges the pages, so a small firm's slug can
  suddenly belong to the acquirer (e.g. "Sankalp" became the `hcltech` page). We watch for this (see §5).
- **"Currently working" = the JANI definition.** A role counts as current if LinkedIn marks it `present`,
  **OR** it has a start date and **no** end date. ⚠️ This is broader than the "normal" present-only definition,
  and this project uses the JANI one **everywhere**. (Full definition in the Appendix.)
- **"ever-worked" vs "currently-working":** ever-worked = anyone who ever had a role there; currently-working =
  only those there now (by the Jani rule). The function filter (§6) is applied to currently-working **only**.
- **Connection filter:** we keep profiles with **≥20 connections** (very low-connection profiles are unreliable);
  Microsoft / Google / Amazon require **≥35**.

## 4. How the people were extracted — the pipeline, step by step
Each track goes through the same seven steps. (Scripts named in brackets live under `scripts\`.)

1. **Resolve company names to LinkedIn pages** (`Track*_CompanyResolve\scripts\resolve_entities.py`).
   We scan the dump and, for each target company, discover the LinkedIn page(s) (slugs) its employees actually
   use, with a profile count for each. Output: a `*_entity_review.csv`.
2. **Confirm the real pages, drop the junk** (`build_confirmed_slugs.py` / `assemble_final_slugs.py`).
   For each company we keep the main page plus closely-related ones (same web domain, or a page with a
   meaningful number of people), and drop pages that are clearly wrong. The kept set is saved as
   **`final_slugs.csv`** — this file is the heart of the pipeline.
3. **Pull the people by page** (`pull_by_slug.py`). We scan the dump again and keep every profile that has a
   role on any confirmed page, storing all of the person's original LinkedIn fields.
4. **Connection filter** (`_common\filter_connections.py`). Keep only profiles with ≥20 connections
   (blanks removed). Produces the `shards_min20conn` set used everywhere afterwards.
5. **Max 3 pages per company** (`_common\apply_top3_cap.py`). If a company has many LinkedIn pages, keep its
   three biggest and drop the long tail (a few big companies with genuine sub-entities are exempted).
6. **Bake the rules into the data** (`_common\finalize_extracted.py`). Physically rewrite the stored profiles
   so only people who still qualify remain. Importantly, a person who works at several target companies is
   **never deleted** — if we exclude one company we simply stop crediting that company, keeping the person for
   the others.
7. **Counting** (`_common\revised_counts.py`, `combined_current_by_city.py`). Count ever-worked and
   currently-working (Jani), per company and per city. All the per-person rules (below) are applied here.

## 5. Special rules for particular companies (and why)
Some companies need special handling, because a blunt slug match would pull the wrong people:
- **KPMG** → keep only the `kpmg-us` page. **PwC** → keep only `pwc-ac-india`. (Their other pages are the
  domestic audit firm, not the GCC.)
- **EY and Deloitte** → only count a person if their profile mentions a GCC/offshore keyword (GDS, GBS, GCC,
  USI, "Global Capability Centre", "Global Delivery", etc.). This separates the global-delivery workforce from
  the domestic consulting firm.
- **Amazon** → ≥35 connections, must be in a known GCC city, and we drop people in domestic-sales roles.
  **Microsoft / Google** → ≥35 connections.
- **NTT Data Group** → Visakhapatnam only. **Teleperformance** → Hyderabad + Gurgaon. **Siemens** →
  Bengaluru/Chennai/Pune/Delhi-NCR. **Philips** → Bengaluru/Chennai/Delhi-NCR.
- **Companies added by mistake, then removed:** "Sankalp Semiconductor" had merged into the **HCLTech** page
  (which dragged in ~420k HCLTech people) — we removed it and physically dropped the HCLTech-only profiles,
  keeping only the people who also worked at a real target company. **Kyndryl** (a GCC *enabler*, not a GCC)
  was removed the same way. **Goldman Sachs** was trimmed to its one real page.
- **Samsung** appeared in both Track-2 and Part-2; per the client we keep it **only in Part-2** and removed the
  Samsung-only people from Track-2.

## 6. The job-function filter (the 11 functions)
The client wants only certain job functions counted: Accounting, Business Development, Consulting, Research,
Engineering, Information Technology, Human Resources, Program/Project Management, Finance, Marketing, Product
Management (+ Customer Service/Support). We classify each person's function from their **job title / headline /
skills** using the Capsight taxonomy (`scripts\_common\gcc_taxonomy_classifier.py`).
- **The function filter is applied to currently-working people only — never to the ever-worked totals.**
- In the done work it was applied to **Track-2 Part-2** and **Maruti**, not to Track-1/Track-2.

## 7. Location — where people actually work
A person's LinkedIn "location" is often their **hometown**, not where they actually work — which made metros
look under-counted. So we compute a **working location** (`scripts\_common\location_normalize.py`):
- Use the **role location** first, fall back to the profile location, else "unlocated".
- Group each metro's suburbs together — e.g. **Delhi-NCR** = Delhi + Gurugram + Noida + Ghaziabad + Faridabad;
  **Mumbai-MMR** = Mumbai + Thane + Navi Mumbai. Other metros: Bengaluru, Hyderabad, Chennai, Pune, etc.
- A **tiered rule** decides which cities count as a company's real centres (bigger companies need a higher share).
- Each tag gets a **confidence**: a current-role location = **High**, a past-role location = **Low**.
- The result is the **`final_location`** column that now sits on every profile in the final file.

## 8. Missing-company recovery
A coverage audit found companies with no matched LinkedIn page (a name-matching miss, not truly absent). The
client supplied LinkedIn URLs for them, and we pulled those pages directly (by the given slug only, ≥20
connections, de-duplicated). Recovered: **26 Track-1 companies, 1 Track-2, 98 Part-2**. Files:
`Recovered_track1_profiles.csv`, `Recovered_track2_profiles.csv`, `Recovered_part2_profiles.csv`, with counts
in `Recovered_companies_counts.csv`. 19 companies still have no working URL (an open item).

## 9. Validation & correction against the GCC master (2026-10-30)
A five-part pass to validate and correct the whole dataset:
1. **Unique company master** (`scripts\_common\build_company_master.py`): de-duplicated all companies across the
   three tracks + the recovered set → **2,510 unique companies** (`Company_Master_List.csv`).
2. **Industry from the GCC master** (`map_industry_from_gcc_master.py`): matched each company to the GCC master
   **by name** (slug only as a fallback) and attached its industry (L1 sector / L2 industry). Result: **2,277
   companies validated**, **197 flagged for review** (not in the master — flagged, never guessed), 36 from the
   Track-1 Excel. (A first attempt matched by slug and mis-tagged big names like Amazon → fixed by matching on
   name first.) → `Company_Master_List_industry.csv`.
3. **Centre mapping** (`company_centre_mapping.py`): for each company, how many people are in each city, and
   whether that city is confirmed by the GCC master → `Company_Centre_Mapping.csv`.
4. **Reconciliation vs targets** (`step4_reconciliation.py`): our currently-working counts (distinct people,
   Delhi-NCR grouped) compared to the GCC-master **minimum** targets, at city / state / industry level →
   `Calibration_match_GCCmaster.csv`.
5. **Quality check** (`Step5_QA_summary.txt`): the main finding is that most industry shortfalls are a
   **classification gap** (the 197 unclassified companies cluster in a few sectors), while **Chennai / Tamil
   Nadu** is the one genuine sourcing gap.

## 10. The results (the numbers)
Distinct people within each track (not de-duplicated across tracks):

| Track | Ever-worked | Currently-working (Jani) |
|---|---:|---:|
| Track-1 (≥20, capped) | 2,770,338 | 1,507,329 |
| Track-2 (≥20, capped, Samsung removed) | 2,603,014 | 1,160,209 |
| Track-2 Part-2 (ever) / (current within the 11 functions) | 1,256,998 | 332,174 |

- **Combined currently-working, distinct people ≈ 3.08 million** — about **99.9%** of the client's calibrated
  total, so the overall numbers match the benchmark closely.
- City/state are broadly on target; the notable real shortfall is **Chennai / Tamil Nadu**.

## 11. The final file
**`AllTracks_profiles_location_tagged.csv.gz`** — **4,861,064 distinct people** (everyone who ever worked at a
target company across all three tracks, one row per person), with all 32 original LinkedIn fields **plus** the
`final_location` column. This is the base for the next deliverable.
> Note: a "~15.9M" figure in some working tables is a count of role-occurrences, **not** people. The real
> headcount is ~4.86M people (≈2.95M currently-working).

## 12. The scripts (where everything lives)
All scripts are under **`scripts\`** in this project (self-contained — no separate workspace needed):
- **`scripts\_common\`** — the shared engines used by every track: `jani_rules.py` (the master rulebook),
  `resolve`/`pull`/`finalize`/`filter_connections`/`revised_counts` (the pipeline), `gcc_taxonomy_classifier.py`
  (functions), `location_normalize.py` (locations), and the validation scripts `build_company_master.py`,
  `map_industry_from_gcc_master.py`, `company_centre_mapping.py`, `step4_reconciliation.py`.
- **`scripts\Track1_CompanyResolve\`, `scripts\Track2_CompanyResolve\`, `scripts\Track2_Part2\`** — each track's
  resolve/pull scripts and its **`final_slugs.csv`** (the confirmed page set).
- **`scripts\MissedCompanies\`, `MarutiSuzuki_Current\`, `Toyota_India\`, `FiveCompanies\`,
  `WalmartGlobalTech_Slug\`, `SlugCheck\`** — the recovery and special-company pulls.

## 13. Key output files (in `\Jani Capsight\`)
- `AllTracks_profiles_location_tagged.csv.gz` — the final 4.86M-person file.
- `Company_Master_List_industry.csv` — the validated company → industry/slugs/tracks master.
- `Company_Centre_Mapping.csv`, `Calibration_match_GCCmaster.csv` — centre mapping + reconciliation.
- `Recovered_*_profiles.csv` — the recovered missing companies.
- The per-track `shards_min20conn` folders — the finalized profile sets.

## 14. Open items
- **197 companies** with unresolved industry — flagged for the client to fill/approve (`Companies_Needing_Industry_Review.csv`).
- **19 companies** still missing a working India LinkedIn URL (`Still_Missing_Companies.xlsx`).
- **140 page-cleaning review pages** await keep/drop adjudication (`reference\pivot_post-spec\StepB_review_bucket.csv`) — from the §16 pivot.

## 15. The next deliverable
Build **one consolidated master profile file**: one row per person, all original columns, **plus** standardized,
validated fields — `final_location`, `company`, `companies_all`, `industry_L1/L2`, `function_L1/L2`,
`matched_master_company`, `classification_status`, `classification_confidence`, `tracks`, `location_confidence`.
Preserve all original data; flag anything that can't be classified confidently rather than guessing. Full
instructions and where each field comes from are in `docs\CONSOLIDATED_FILE_SPEC.md`.

## 16. The accuracy-first pivot (after the spec)
After the spec above, we started an **accuracy-first reclassification** to check whether the reconciliation
shortfalls (e.g. Chennai 54%, Tamil Nadu 57%) were real gaps or a measurement artifact — then **paused it to
build this handoff**. It sits on top of everything above and refines HOW the next file (§15) should be built.
Full account: **`docs\POST_SPEC_PIVOT_accuracy_first.md`**; frozen rules:
`reference\pivot_post-spec\GCC_Classification_Methodology_LOCK.md`; scripts: `scripts\PostSpec_Pivot\`.
What it established (a 6-company pilot proved each point):
- **Map people to their WORKING location** (role location, not hometown). This flips the metro "gaps" to
  overshoot (Std Chartered Chennai 314%, Ford 165%) — the shortfalls were mostly a measurement artifact.
- **Don't trust the GCC master's LinkedIn-URL column — it's corrupt.** Anchor company identity on the master
  **NAME** and OUR own resolved slugs. (The old "re-pull pages from the master URL" idea is cancelled.)
- **Clean each company's pages** by how well the people on them match the company: ≥60% keep, <20% drop, the
  middle → a 140-page human-review bucket (`StepB_review_bucket.csv`). Acquisitions/renames (Vodafone→vois,
  etc.) are kept; genuine wrong-company pollution is dropped — never auto-dropped.
- **Benchmark counts foreign-captive GCCs only** — Indian-HQ firms (Zoho) and service-providers
  (EXL/Virtusa/Teleperformance/CGI) stay in the file but are flagged out of the benchmark.
- **Classification status per dimension = Correct / Needs Correction / Unverified** (+ source), dimensions
  independent, nothing forced.
- The 12 standardized fields in §15 were further specified in the answer-box prompts (see the chat history):
  `company` = current/latest target employer, `companies_all` = every matched target company; include & recover
  the ~370k location-less profiles rather than dropping them; `classification_confidence` is replaced by the
  Correct/Needs-Correction/Unverified status.
- **To resume:** adjudicate the 140 review pages → rebuild the 12-field master on the cleaned slugs → re-run
  the city/state/industry/function reconciliation on working location. (Note: a "15.9M" figure that appears in
  this work is role-occurrences, not people — the real totals are ~4.86M ever-worked / ~2.95M current.)

---

## Appendix — key definitions & original instructions

**"Currently working" (Jani's logic):** a role counts as current if `duration.present` is true, OR it has a
start date and no end date. (Broader than the normal "present-only" rule; used everywhere in this project.)

**The 11 job functions to keep:** Accounting, Business Development, Consulting, Research, Engineering,
Information Technology, Human Resources, Program & Project Management, Finance, Marketing, Product Management,
plus Customer Service/Support (but not domestic after-sales / sales-support). Applied to currently-working only.

**Location rule:** working location = role location → profile location → unlocated; metros grouped
(Delhi-NCR, Mumbai-MMR, …); a tiered share decides a company's real centres; current-role location = High
confidence, past-role = Low.

**Benchmark:** the GCC master list's per-city/state/industry numbers are **minimum** expectations; being over
target is fine.
