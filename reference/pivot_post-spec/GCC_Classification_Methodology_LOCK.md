# GCC Profile Classification — LOCKED METHODOLOGY (company-first + profile-level validation)
_Created 2026-10-30. This is the frozen rule-set for the accuracy-first reclassification of the GCC profile
pool, agreed after the 6-company pilot. Scale step applies these rules to all companies, then re-runs the
city / state / industry / function reconciliation. Supersedes the raw-profile-location calibration in
`Calibration_match_GCCmaster.csv` for all location work going forward._

## WHY (pilot conclusion, 2026-10-30)
Piloted on 6 companies across industries + the shortfall metros (Standard Chartered, Ford, Caterpillar,
Zoho, Omega Healthcare, Target). Scripts/outputs: scratchpad `pilot_centre_coverage.py` →
`pilot_centre_coverage.csv` + `pilot_slug_validation.csv`.
- **The metro shortfalls were a MEASUREMENT artifact, not a sourcing gap.** Mapping people to their actual
  WORKING location (role location, not profile hometown) flips Chennai from the old 54% to 165–314% for the
  Chennai-heavy pilot companies (Std Chartered Chennai 314%, Ford 165%, Caterpillar 202%). Role location was
  available for 64–73% of current profiles.
- **Company-first slug validation catches real pollution:** AstraZeneca was merged under Standard Chartered
  (4,851 wrong current profiles); construction/retail firms merged under Target. Also surfaced genuinely
  ambiguous pages (`construction-ai` ↔ Caterpillar India) for manual review.
- **The master is not infallible either:** Omega Healthcare — master puts all 10,074 in Hyderabad, but the
  real workforce is Chennai/Trichy/Bengaluru/Coimbatore (master single-city attribution wrong). Zoho —
  master lists 154 (Indian-HQ firm, not a captive GCC; benchmark meaningless).
- **OUR track-resolved pages are authoritative; the master URL is NOT** (user direction 2026-10-30). What
  looked in the pilot like "we pulled the wrong page" (Target `target` vs master `target-in-india`; Omega
  `omega-healthcare-management-services` vs master `omega-healthcare`) is the master URL column being wrong,
  not us. Our pages stand. Where the master's city attribution disagrees with our page (e.g. Omega = all
  Hyderabad in master, but Chennai/Trichy-spread in our data), OUR working-location distribution is trusted;
  the master contributes only the benchmark TOTAL, matched by name.

## LOCKED RULES
1. **Currently working** = Jani: `duration.present` is True OR (`duration.start` set AND no `duration.end`).
   Overshoot vs target is acceptable — targets are MINIMUM benchmarks. (User-confirmed 2026-10-30.)
2. **Working location** (the location used for all city/state tallies and reconciliation):
   role location of the matched company role FIRST → profile location (`miniprofile_location_address` +
   `_region`) fallback → `UNLOCATED`. canon_city grouping; **Delhi-NCR grouped**; multiple centres within a
   state kept SEPARATE. (Replaces profile-own-location in the old calibration.)
3. **Company identity (company-first)**: anchor on the master **COMPANY NAME** (col 1 + col 2 "LinkedIn
   Specific Name(s)"). The master's **LinkedIn Entity URL column (col 3) is NOT USED AT ALL** — it is
   CORRUPTED/misaligned (e.g. Honeywell cell = `decathlon-group`, Aegon = `logixal-inc`, Advantech =
   `synchrony-financial`) and the user has directed us not to trust it (2026-10-30). LinkedIn pages come ONLY
   from OUR OWN resolved slugs (from real dump scans). The master contributes benchmark headcounts, industry,
   Global-HQ and per-city numbers, joined by NAME only. Accepted slug set = our resolved pages, minus pollution
   and with ambiguous pages sent to review (rule 4). Connection floor conn≥20 retained.
4. **Ambiguous slug rule** (user-confirmed): keep a sibling slug if ≥~60% of its profiles' `company.name`
   normalizes to the company; <~20% → drop; in between → **manual-review bucket** for sign-off. Each
   decision recorded with evidence (profile count + top company names).
5. **Re-pull authoritative pages** — CANCELLED (2026-10-30, user direction). The master URL column is wrong,
   so there is NO master-URL-driven re-pull. We work from our already-pulled pages. If a company's India
   presence ever needs a missing page added, it is found by NAME-based discovery on the dump, never from the
   master URL. (The earlier 646 / 213 "re-pull" lists were artifacts of the bad column and are discarded.)
6. **Per-dimension classification status** (user-confirmed): each of company / location / industry / function
   gets `Correct` / `Needs Correction` / `Unverified`, with the **source** recorded. Dimensions handled
   INDEPENDENTLY — a profile is never dropped because one dimension is missing. Nothing forced; insufficient
   evidence → Unverified / manual review.
7. **Industry** from the validated GCC-master mapping (name-first, slug fallback); the 197 "unclassified"
   are re-examined — those actually in the master under a different name (e.g. Target = "Target Corporation")
   are RECOVERED by alias/slug/fuzzy + the master's own LinkedIn-URL slug; those genuinely absent are flagged.
8. **Function** from the Capsight taxonomy Excel (`Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx`) native
   L1/L2, classified on job title/designation (+headline/skills); domestic → OUT_OF_SCOPE, unusable → NOISE.

## BENCHMARK NUMERATOR (resolved 2026-10-30, user-confirmed)
- **Count only foreign-captive GCCs.** EXCLUDE from benchmark totals: Indian-HQ firms (master Global HQ =
  India, e.g. Zoho) and pure service-providers absent from the master (EXL/Virtusa/Teleperformance/CGI).
  These stay in the consolidated profile file but are FLAGGED (`benchmark_eligible = No`, with reason
  Indian-HQ / not-in-master), never in the GCC benchmark numerator.

## SCALE PLAN (after the pending decision)
A. Reconcile every company's slugs vs master (company-first); build accepted + review + drop sets; re-pull
   missing master pages from the dump. →  per-company slug decision file.
B. Re-scan the pulled + re-pulled profiles once; emit the consolidated master profile file (one row per uid,
   all original cols + the 12 standardized fields from the agreed schema) with per-dimension status+source.
C. Re-run city / state / industry / function reconciliation on WORKING location vs GCC-master minimums,
   Delhi-NCR grouped, distinct-uid, benchmark numerator per the pending decision. →  corrected calibration.
D. Report: classification-error-vs-real-gap split per level; remaining genuine gaps.
