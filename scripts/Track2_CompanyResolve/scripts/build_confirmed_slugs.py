# Purpose: TRACK-2 version of Track-1's build_confirmed_slugs. From track2_entity_review.csv, auto-confirm
#   each company's real LinkedIn slug(s): keep the dominant slug (most profiles) + any slug sharing its
#   domain + any other slug with a meaningful count; drop no-slug and junk. FLAG the hard ones for review:
#   very short/ambiguous target names (<=4 chars, slug differs) and weak ones (dominant slug tiny). Writes
#   confirmed_slugs.csv (ready to pull) + flagged_companies.csv (need a quick look).
import csv, os, re
from collections import defaultdict


def squash(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve"
REVIEW = os.path.join(OUT_DIR, "track2_entity_review.csv")
CONFIRMED = os.path.join(OUT_DIR, "confirmed_slugs.csv")
FLAGGED = os.path.join(OUT_DIR, "flagged_companies.csv")
JUNK = {"", "forage", "theforage", "the-forage", "results", "forage-", "forageofficial"}

rows = list(csv.DictReader(open(REVIEW, encoding="utf-8")))
by = defaultdict(list)
for r in rows:
    by[r["company_target"]].append(r)

conf_rows = []
flagged_rows = []
for t, rs in by.items():
    label = rs[0]["company_label"]
    cand = [(r["linkedin_slug"], int(r["n_profiles"]), r["domain"], r["example_name"]) for r in rs
            if r["linkedin_slug"] not in JUNK]
    if not cand:
        flagged_rows.append((t, label, "", 0, "", "no slug discovered"))
        continue
    cand.sort(key=lambda x: -x[1])
    dom_slug, dom_n, dom_domain, dom_name = cand[0]
    confirmed = {}
    for slug, n, dom, name in cand:
        keep = (slug == dom_slug) or (dom_domain and dom == dom_domain) or (n >= max(10, 0.05 * dom_n))
        if keep:
            confirmed[slug] = (n, dom, name)
    short = len(t) <= 4
    weak = dom_n < 30
    slug_is_name = squash(dom_slug) == squash(t)
    if weak:
        flagged_rows.append((t, label, dom_slug, dom_n, dom_domain, "weak (dominant <30)"))
    elif short and not slug_is_name:
        flagged_rows.append((t, label, dom_slug, dom_n, dom_domain, "short name, slug differs - CHECK"))
    else:
        for slug, (n, dom, name) in sorted(confirmed.items(), key=lambda x: -x[1][0]):
            conf_rows.append((t, label, slug, f"https://www.linkedin.com/company/{slug}/", dom, n,
                              "dominant" if slug == dom_slug else "sibling"))

with open(CONFIRMED, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    w.writerow(["company_target", "company_label", "linkedin_slug", "linkedin_url", "domain", "n_profiles_discovered", "role"])
    w.writerows(conf_rows)
with open(FLAGGED, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    w.writerow(["company_target", "company_label", "dominant_slug", "dominant_n", "dominant_domain", "flag_reason"])
    w.writerows(flagged_rows)

ncomp_conf = len(set(r[0] for r in conf_rows))
print(f"companies auto-confirmed: {ncomp_conf} | confirmed slugs: {len(conf_rows)} -> {os.path.basename(CONFIRMED)}")
print(f"companies flagged for review: {len(flagged_rows)} -> {os.path.basename(FLAGGED)}")
from collections import Counter
rc = Counter(r[5] for r in flagged_rows)
print("flag reasons:", dict(rc))
print("\nsample flagged:")
for t, lab, ds, dn, dd, rsn in flagged_rows[:20]:
    print(f"  {lab[:34]:34s} dominant={ds[:24]:24s} n={dn:<6} [{rsn}]")
