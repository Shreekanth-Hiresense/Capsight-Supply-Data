# DATA STRUCTURE — ziplabs passive_IN + our extracted files

_Self-contained reference. You do not need any other machine config to understand this._

## 1. The raw source (READ-ONLY, you rarely touch it directly)
`ziplabs passive_IN` = India LinkedIn candidate/supply profiles. **This is the ONLY ziplabs dataset used.**
The separate `ziplabs_companies_*` dataset is **NOT used anywhere** in this project (it was tried once for
company resolution, found noisy with empty domains, and abandoned — company resolution is done entirely from
the profiles themselves).

- Format: gzip-compressed **JSON Lines** (`.jsonl.gz`), one JSON object = one person per line, 100% India.
- `uid` = the LinkedIn public slug and the **PRIMARY KEY / identity**. One row per person, no duplicates,
  no "deleted" column. `url` = `https://www.linkedin.com/in/<uid>/`.
- The India pool = all `ziplabs_passive_IN_*` folders read together, deduped on `uid` (newest folder wins).
- READ-ONLY: never write/edit/rename/delete inside the ziplabs tree. Write all outputs elsewhere.

### Per-profile fields that matter here
- `miniprofile`: `name`, `first/last_name`, `headline` (99.6% filled — the backbone of any text search),
  `summary` (~18%), `connections`, `followers`, and `location {address, region(=state), ...}`.
  `address` is lowercase free text "city, state, india"; city = first comma-token when 3 tokens.
- `experience[]` (list; ~64% have ≥1): each role has `title` (free text, dirty), `company {name, domain,
  **lnkd_uid (= company slug)**, lnkd_url1, lnkd_url2}`, `location` (role/work location), and
  `duration {start, end, present}` — **always use `duration`, never parse `date1`/`date2`**.
- `education[]`, `skill[]` (flat list), `certification[]`, `language[]`, `project[]`, etc.
- There is **no** industry / management-level / company-size / total-experience field on the profile.
  Industry comes from the **GCC master list** (see reference/), joined by company NAME.

## 2. How we match a profile to a company — SLUG, not name
Each role carries `company.lnkd_uid` and `company.lnkd_url1/2`. The **slug** = the `/company/<slug>` segment
(or `lnkd_uid`). We match a profile to a target company by **exact slug**, never by display name — this
catches differently-named entities (e.g. "J.P. Morgan" people sit on the `jpmorganchase` page).
⚠️ Acquisitions merge LinkedIn pages, so a small firm's slug can become the acquirer's (Sankalp→`hcltech`,
Infinera→`nokia`). Watch for a tiny company whose slug pulls a huge count. See documentation §9.

## 3. Our extracted files (what you actually work with)
All one row per person, **all 32 original LinkedIn columns preserved**, gzip or plain CSV.

### The final file (the base for everything next)
`AllTracks_profiles_location_tagged.csv.gz` — 8.1 GB, **4,861,064 distinct uids** (everyone ever-worked at a
target company across all three tracks, deduped to one row per uid). **33 columns = the 32 original + `final_location`.**

The 33 columns, in order:
```
uid, url, image_url, updated_at,
miniprofile_name, miniprofile_first_name, miniprofile_last_name, miniprofile_headline,
miniprofile_summary, miniprofile_connections, miniprofile_followers,
miniprofile_location_address, miniprofile_location_country, miniprofile_location_country_code,
miniprofile_location_region, miniprofile_location_state_code, miniprofile_s_name, miniprofile_gender,
miniprofile_linkedinurl, experience, education, skill, certification, language, project, patent,
award, course, volunteer, recomm_received, recomm_given, interest, final_location
```
- `experience` (and the other list columns) are stored as a **Python-repr string** — parse with
  `ast.literal_eval`, not `json.loads`.
- `final_location` = canonical work-city (see documentation §11.5): grouped metros such as `bengaluru`,
  `delhi ncr`, `mumbai mmr`, `hyderabad`, `pune`, `chennai`, `kolkata`, ... Built from role/profile location
  with a tiered per-company cap; current-role location → High confidence, past-role → Low (that confidence is
  recorded in `reference/Company_Location_Normalized_profiles.csv`). Rows with no evidence were excluded from
  the location tally, so a small share of rows can have a blank `final_location`.

### Supply (per-track pulls — the inputs that produced the final file)
- `Track1_BySlug_profiles\shards_min20conn\` + `_sidecars\`
- `Track2_BySlug_profiles\shards_min20conn\` + `_sidecars\` (Samsung removed — kept only in Part-2)
- `Track2_Part2_profiles\shards\` + `_sidecars\`
- `Recovered_track1/track2/part2_profiles.csv` — the "missing companies" we recovered later
- `DEShaw_both_conn10.csv`, `Big4_curated\` — special pulls
- `_sidecars` = uid → matched-slug maps for each shard set.

Read big `.gz` files by **streaming shard-by-shard** (see 00_START_HERE "Performance"). Never load the 8 GB
file into pandas at once.
