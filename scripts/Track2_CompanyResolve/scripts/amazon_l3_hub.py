# Purpose: L3 breakdown of the Amazon HUB currently-working pool (the 85,420 = currently working at the
#   'amazon' page under Jani's logic AND in one of the 7 hub cities, from the Track-2 pulled shards).
#   Reuses the SAME L3 keyword rules + JSON taxonomy as amazon_l3_classify.py: classify each person's
#   qualifying current Amazon role title into one of Amazon's 50 L3 roles, count per L3/L2/L1 vs the JSON
#   audited target, and list the top unmatched titles. Read-only; writes a summary txt + counts CSV.
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common\GCC_Headcount_Extraction\scripts")
from amazon_l3_classify import L3_KEYWORDS, classify  # noqa: E402

JSON_PATH = r"C:\Users\LENOVO\Downloads\Capsight_GCC_Ecosystem_Platform_Data.json"
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve"
WORKERS = 15
AMAZON_SLUGS = {"amazon"}

# the updated JSON renamed several Amazon L3 roles; map old keyword-rule names -> current JSON names
RENAME = {
    "BI & Data Visualization Development": "Data Visualization Development",
    "Commercial Intelligence & Pricing Analytics": "Pricing Analytics",
    "Pricing Analytics Optimization": "Pricing Analytics",
    "Compensation & Benefits Analytics": "Compensation & Benefits",
    "HR Business Partnering (HRBP)": "HRBP",
    "Logistics & Freight Operations Engineering": "Logistics & Freight Operations",
    "Marketing Mix Modeling (MMM)": "Marketing Mix Modeling",
    "People Analytics & Metrics": "People Analytics",
    "Regulatory Compliance Governance": "Regulatory Compliance",
    "Search, Ranking & Discovery Engineering": "Search & Recommendation Engine",
    "Site Reliability Engineering (SRE)": "Site Reliability Engineering",
    "Technical Account Management (TAM)": "Technical Account Management",
    "Technical Product Management (PM-T)": "Technical Product Management",
    "UX/UI Product Design": "Product Design",
    "Warehouse Automation & Robotics Software Engineering": "Warehouse Robotics Software Engineering",
}

HUBS = {
    "hyderabad": ["hyderabad", "secunderabad"], "mumbai": ["mumbai", "navi mumbai", "thane"],
    "chennai": ["chennai"], "bengaluru": ["bengaluru", "bangalore"], "pune": ["pune"],
    "delhi ncr": ["delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad"],
    "coimbatore": ["coimbatore"],
}
HUB_TOKENS = [t for v in HUBS.values() for t in v]


def hub_hit(text):
    t = (text or "").lower()
    return any(tok in t for tok in HUB_TOKENS)


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    return (u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()) or None


def role_slugs(c):
    s = set()
    if c.get("lnkd_uid"):
        s.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        sl = slug_from_url(c.get(k))
        if sl:
            s.add(sl)
    return s


def worker(path):
    l3c = Counter(); unmatched = Counter(); n_gated = 0; n_notitle = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            if not isinstance(exp, list):
                continue
            prof_hub = hub_hit((row.get("miniprofile_location_address") or "") + " " +
                               (row.get("miniprofile_location_region") or ""))
            qualifying = []   # (present_flag, start, title) of current+hub amazon roles
            for e in exp:
                if not isinstance(e, dict) or not (role_slugs(e.get("company") or {}) & AMAZON_SLUGS):
                    continue
                dur = e.get("duration") or {}
                present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                is_jani_cur = present or ((not end) and start)
                if not is_jani_cur:
                    continue
                if prof_hub or hub_hit(e.get("location") or ""):
                    qualifying.append((present, start or "", e.get("title")))
            if not qualifying:
                continue
            n_gated += 1
            # pick title: prefer a present role, else latest-start
            qualifying.sort(key=lambda x: (x[0], x[1]), reverse=True)
            title = qualifying[0][2]
            if not title:
                n_notitle += 1
                continue
            l3 = classify(title)
            if l3:
                l3c[l3] += 1
            else:
                unmatched[title.strip().lower()] += 1
    return l3c, unmatched, n_gated, n_notitle


def load_meta():
    data = json.load(open(JSON_PATH, encoding="utf-8"))
    amz = next(r for r in data if r["company_name"] == "Amazon")
    meta = {}
    for x in amz["l3_role_decomposition"]:
        meta[x["l3_role_name"]] = (x["l1_functional_domain"], x["l2_job_family"],
                                   x["audited_headcount"], x["share_of_talent_pct"])
    return meta


def main():
    meta = load_meta()
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"shards {len(shards)} | workers {WORKERS}", flush=True)
    L3 = Counter(); UN = Counter(); GATED = 0; NOTITLE = 0
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for l3c, un, ng, nt in pool.imap_unordered(worker, shards):
            L3.update(l3c); UN.update(un); GATED += ng; NOTITLE += nt
    # reconcile keyword-rule names with current JSON taxonomy names
    L3n = Counter(); off_tax = 0
    for l3, c in L3.items():
        l3m = RENAME.get(l3, l3)
        if l3m in meta:
            L3n[l3m] += c
        else:
            off_tax += c
    L3 = L3n
    matched = sum(L3.values()); unm = sum(UN.values())
    l1c = Counter(); l2c = Counter()
    for l3, c in L3.items():
        l1, l2, _, _ = meta[l3]; l1c[l1] += c; l2c[(l1, l2)] += c
    lines = []
    def p(s=""):
        print(s); lines.append(s)
    p(f"HUB current Amazon pool (the 85k)   : {GATED:,}")
    p(f"  matched to an L3 role             : {matched:,} ({100*matched/GATED:.1f}%)")
    p(f"  unmatched current title           : {unm:,} ({100*unm/GATED:.1f}%)")
    p(f"  no current title                  : {NOTITLE:,}")
    p("\n==== L1 breakdown (matched) ====")
    for l1 in sorted(l1c, key=lambda k: -l1c[k]):
        p(f"  {l1c[l1]:7,}   {l1}")
    p("\n==== L3 breakdown (pool matched vs Amazon JSON target), sorted by pool ====")
    for l3, c in sorted(L3.items(), key=lambda kv: -kv[1]):
        l1, l2, tgt, sh = meta[l3]
        p(f"  {c:6,}   (json target {tgt:6,})   [{l1} > {l2}]  {l3}")
    p("\n==== L3 roles with ZERO matches in pool ====")
    for l3, (l1, l2, tgt, sh) in sorted(meta.items(), key=lambda kv: -kv[1][2]):
        if L3.get(l3, 0) == 0:
            p(f"  0   (json target {tgt:6,})   {l3}")
    p("\n==== TOP 30 UNMATCHED titles ====")
    for t, c in UN.most_common(30):
        p(f"  {c:6,}  {t}")
    with open(os.path.join(OUT_DIR, "amazon_hub_l3_summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    with open(os.path.join(OUT_DIR, "amazon_hub_l3_counts.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["l1", "l2", "l3_role", "pool_matched", "json_target_hc", "json_share_pct"])
        for l3, (l1, l2, tgt, sh) in sorted(meta.items(), key=lambda kv: -kv[1][2]):
            w.writerow([l1, l2, l3, L3.get(l3, 0), tgt, sh])
    print(f"\n[{time.time()-t0:,.0f}s] -> amazon_hub_l3_counts.csv")


if __name__ == "__main__":
    main()
