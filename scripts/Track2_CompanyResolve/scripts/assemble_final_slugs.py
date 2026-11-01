# Purpose: Build the COMPLETE Track-2 slug set to pull by. Applies the same keep rule as
#   build_confirmed_slugs (dominant + same-domain siblings + any slug with a meaningful count) to EVERY
#   company in track2_entity_review.csv -- including the 24 flagged ones (reviewed: their dominant slugs
#   are correct, just name-variants). Drops junk slugs and no-slug rows. Writes final_slugs.csv.
import csv, os, re
from collections import defaultdict

OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve"
REVIEW = os.path.join(OUT_DIR, "track2_entity_review.csv")
FINAL = os.path.join(OUT_DIR, "final_slugs.csv")
JUNK = {"", "forage", "theforage", "the-forage", "results", "forage-", "forageofficial"}

rows = list(csv.DictReader(open(REVIEW, encoding="utf-8")))
by = defaultdict(list)
for r in rows:
    by[r["company_target"]].append(r)

out = []
for t, rs in by.items():
    label = rs[0]["company_label"]
    cand = [(r["linkedin_slug"], int(r["n_profiles"]), r["domain"], r["linkedin_url"]) for r in rs
            if r["linkedin_slug"] not in JUNK]
    if not cand:
        continue
    cand.sort(key=lambda x: -x[1])
    dom_slug, dom_n, dom_domain, _ = cand[0]
    for slug, n, dom, url in cand:
        keep = (slug == dom_slug) or (dom_domain and dom == dom_domain) or (n >= max(10, 0.05 * dom_n))
        if keep:
            out.append((t, label, slug, url, dom, n, "dominant" if slug == dom_slug else "sibling"))

with open(FINAL, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    w.writerow(["company_target", "company_label", "slug", "linkedin_url", "domain", "n_profiles_discovered", "role"])
    w.writerows(out)

ncomp = len(set(r[0] for r in out))
print(f"final: {ncomp} companies | {len(out)} slugs -> {os.path.basename(FINAL)}")
