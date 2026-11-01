# POST-SPEC PIVOT — the accuracy-first reclassification

> **Read this AFTER the main documentation.** Everything here happened **after** the 12-field
> consolidated-file spec (~00:30–06:06 2026-10-30) but **before** the project was handed off. The pre-spec
> pipeline (tracks → recovery → location → validation → the 4.86M final file) is unchanged and remains the
> foundation — this pivot sits ON TOP of it and refines how the next deliverable is built.

---

## 1. Why the pivot started
The Step-4/5 reconciliation (documentation §12) showed **city/sector shortfalls** vs the GCC-master minimum
targets — e.g. Chennai 54%, Hyderabad 74%, Tamil Nadu 57%, and sector gaps in Logistics/Consulting/Healthcare.
The question was: are these **real sourcing gaps**, or **measurement artifacts**? A 6-company pilot was run to
find out, and it changed how location and company identity are handled.

## 2. The pilot (6 companies)
Companies: **Standard Chartered, Ford, Caterpillar, Zoho, Omega Healthcare, Target** (chosen across industries
and the shortfall metros). Scripts/outputs: `scripts/PostSpec_Pivot/pilot_centre_coverage.py` →
`reference/pivot_post-spec/pilot_centre_coverage.csv` + `pilot_slug_validation.csv`.

**Findings:**
- **The metro shortfalls were largely a MEASUREMENT artifact, not a sourcing gap.** Mapping people to their
  actual **working location** (role location, not profile hometown) flips Chennai from ~54% to **165–314%**
  for the Chennai-heavy pilot companies (Std Chartered Chennai 314%, Ford 165%, Caterpillar 202%). Role
  location was available for 64–73% of current profiles.
- **Company-first slug validation catches real pollution:** AstraZeneca was wrongly merged under Standard
  Chartered (~4,851 wrong current profiles); construction/retail firms merged under Target; `construction-ai`
  is a genuinely ambiguous page (↔ Caterpillar India) needing manual review.
- **The GCC master is not infallible either:** Omega Healthcare — master puts all 10,074 in Hyderabad, but
  the real workforce spreads across Chennai/Trichy/Bengaluru/Coimbatore. Zoho — master lists 154, but it is an
  **Indian-HQ** firm, not a foreign captive, so that benchmark is meaningless.
- **The master's LinkedIn Entity URL column is CORRUPT/misaligned** (e.g. Honeywell cell = `decathlon-group`,
  Aegon = `logixal-inc`, Advantech = `synchrony-financial`). Owner direction (2026-10-30): **do not trust the
  master URL column at all.** Our own track-resolved slugs are authoritative; the master contributes only the
  benchmark TOTAL / industry / Global-HQ / per-city numbers, joined **by company NAME**.

## 3. The LOCKED methodology (the frozen rule-set)
Full text: **`reference/pivot_post-spec/GCC_Classification_Methodology_LOCK.md`**. Summary of the locked rules:
1. **Currently working = Jani** (`duration.present` True OR start set & no end). Overshoot vs a target is fine —
   targets are minimums.
2. **Working location** = matched company role's location → profile location fallback → `UNLOCATED`; canon_city
   grouping, **Delhi-NCR grouped**, multiple centres within a state kept **separate**. (This replaces
   profile-own-location in the old calibration — it is the fix that closed the metro "gap".)
3. **Company identity = company-first:** anchor on the master **company NAME** (cols 1–2). The master
   **LinkedIn URL column (col 3) is NOT used** (corrupt). LinkedIn pages come only from OUR resolved slugs.
4. **Ambiguous slug rule:** keep a sibling page if **≥~60%** of its profiles' `company.name` normalizes to the
   company; **<~20% → drop**; in between → **manual-review bucket**, each decision recorded with evidence.
5. **Re-pull from master URL = CANCELLED** (the URL column is wrong). Missing pages, if ever needed, are found
   by NAME-based discovery on the dump — never from the master URL. The earlier 646/213 "re-pull" lists are
   discarded as artifacts of the bad column.
6. **Per-dimension classification status:** each of company / location / industry / function gets
   **`Correct` / `Needs Correction` / `Unverified`**, with the **source recorded**. Dimensions are independent;
   a profile is never dropped because one dimension is missing; nothing is forced (insufficient evidence →
   Unverified / review).
7. **Industry** from the validated GCC-master mapping (name-first, slug fallback); the 197 "unclassified" are
   re-examined and recovered by alias/fuzzy where they're really in the master under another name; genuine
   absences flagged.
8. **Function** from the Capsight taxonomy Excel native L1/L2, on job title (+headline/skills); domestic →
   OUT_OF_SCOPE, unusable → NOISE.

## 4. The benchmark numerator decision (owner-confirmed)
**Count only foreign-captive GCCs toward the benchmark.** EXCLUDE from the benchmark totals: Indian-HQ firms
(master "Global HQ" = India, e.g. Zoho) and pure service-providers absent from the master (EXL / Virtusa /
Teleperformance / CGI). They **stay in the profile file but are FLAGGED** (`benchmark_eligible = No`, with
reason), so nothing is lost — they just don't distort city/sector benchmark coverage. (The owner chose the
recommended option: *"i am going with the recommended action here."*)

## 5. What was actually built (Step A, Step B)
- **Step A — slug reconciliation.** `scripts/PostSpec_Pivot/stepA_slug_reconcile.py` →
  `reference/pivot_post-spec/StepA_slug_reconciliation.csv` — our resolved slugs matched to master company
  names (company-first), the basis for accept/review/drop.
- **Step B — page-cleaning scan.** `scripts/PostSpec_Pivot/stepB_page_clean.py` → `StepB_slug_decisions.csv`
  (all 4,674 pages: keep/review tag + match fraction + the real LinkedIn names on each) and
  `StepB_review_bucket.csv` (the **140 pages needing human judgment**). Result: **4,434 pages auto-kept**,
  **140 → review**, 95 empty. The 140 are a MIX — most should be KEPT (acquisitions / renames / GCC sub-brands,
  e.g. Vodafone→`vois`, NatWest→`royal-bank-of-scotland`, Broadcom→`symantec`/`vmware`, Oracle→`sun-microsystems`),
  a minority are genuine pollution to DROP (Atos→`cms-infosystems`, Agilent→`abc-consultants`,
  ArcelorMittal→`essar-steel`, AstraZeneca-under-Standard-Chartered). The rule deliberately **never
  auto-drops** these — distinguishing "acquired brand" from "wrong company" needs real-world knowledge.

### ⚠️ Important number correction
A table in this work showed "~15.9M" for the "keep" pages. **That is NOT 15.9 million people** — it is a
sum of **role-occurrences across pages** (one person counted on every company page they ever worked at, and
twice if in two tracks). The true figures are **~4.86M distinct people ever-worked** and **~2.95M currently
working (Jani)**. The 15.9M was only ever used to gauge relative page sizes for the keep/drop check.

## 6. What is PENDING (where the next person resumes, if continuing the pivot)
The pivot was **paused here** to build this handoff. The remaining steps (from the LOCK's scale plan):
- **Adjudicate the 140 review pages** — produce a keep/drop + reason for each in `StepB_review_bucket.csv`,
  for owner sign-off. (This was the open question when the pivot was paused.)
- **Step C — rebuild the consolidated master profile file** (one row per uid, all original columns + the 12
  standardized fields from `CONSOLIDATED_FILE_SPEC.md`, with per-dimension status + source), using the cleaned
  slug set.
- **Step D — re-run city/state/industry/function reconciliation** on WORKING location vs the GCC-master
  minimums (Delhi-NCR grouped, distinct-uid, foreign-captive numerator), and report the
  **classification-error-vs-real-gap split** per level.

## 7. Open items carried from the pilot
- 140 review-bucket pages await adjudication (`StepB_review_bucket.csv`).
- 197 companies with unresolved industry (owner review).
- 19 companies still missing a working India LinkedIn URL.

---
**Relationship to the main docs:** `CONSOLIDATED_FILE_SPEC.md` (the 12 fields) is still the target file; this
pivot refines HOW it's built (cleaned slugs, working-location, per-dimension status, foreign-captive numerator).
If anything here conflicts with the pre-spec calibration, the LOCK rules win for location/company-identity work.
