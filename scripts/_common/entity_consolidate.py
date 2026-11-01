# Purpose: "Max 3 entity pages per company" consolidation + recount, for Track-1 or Track-2 (TRACK env).
#   1) True unique-profile count per entity-page SLUG from the pulled sidecars (uid -> matched_slugs).
#   2) Map each slug to its parent company (final_slugs.csv). Rank a company's slugs by unique-profile
#      count desc; KEEP top 3, ARCHIVE the rest (companies with <=3 keep all).
#   3) Write top3_slugs.csv + archived_slugs.csv (NEW files; final_slugs.csv is NOT overwritten).
#   4) Recount over the pulled shards using ONLY the top-3 slug set: distinct profiles EVER, currently
#      working NORMAL (duration.present) and JANI (present OR start-but-no-end). Profiles are de-duplicated
#      (one row per uid; a person at >1 retained page counts once).
#   Usage: TRACK=track1 python entity_consolidate.py   (or TRACK=track2)
import ast, csv, glob, gzip, json, os, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(
        final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
        company_col="company",
        side=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\_sidecars",
        shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards",
        out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve"),
    "track2": dict(
        final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
        company_col="company_target",
        side=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\_sidecars",
        shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards",
        out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or TRACK=track2")
C = CFG[TRACK]
WORKERS = 15
TOP3 = None  # set in worker init


def slug_company_map():
    m = {}
    for r in csv.DictReader(open(C["final"], encoding="utf-8")):
        sl = (r.get("slug") or "").strip().lower()
        comp = (r.get(C["company_col"]) or "").strip()
        if sl:
            m.setdefault(sl, comp)   # first company wins if a slug appears twice
    return m


def count_per_slug():
    # distinct uid per slug from sidecars (uids disjoint across shards -> counts sum)
    cnt = Counter()
    for sp in glob.glob(os.path.join(C["side"], "*.side.gz")):
        with gzip.open(sp, "rt", encoding="utf-8", newline="") as f:
            rd = csv.reader(f); next(rd, None)
            for row in rd:
                if len(row) < 2:
                    continue
                for sl in row[1].split("|"):
                    sl = sl.strip().lower()
                    if sl:
                        cnt[sl] += 1
    return cnt


def build_top3():
    s2c = slug_company_map()
    cnt = count_per_slug()
    by_comp = defaultdict(list)
    for sl, comp in s2c.items():
        by_comp[comp].append((sl, cnt.get(sl, 0)))
    keep, arch = [], []
    for comp, slugs in by_comp.items():
        slugs.sort(key=lambda x: -x[1])
        for i, (sl, n) in enumerate(slugs):
            (keep if i < 3 else arch).append((comp, sl, n, "keep" if i < 3 else "archived"))
    with open(os.path.join(C["out"], "top3_slugs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "slug", "unique_profiles", "status"])
        w.writerows(sorted(keep, key=lambda x: (x[0], -x[2])))
    with open(os.path.join(C["out"], "archived_slugs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "slug", "unique_profiles", "status"])
        w.writerows(sorted(arch, key=lambda x: (x[0], -x[2])))
    top3 = {sl for _, sl, _, _ in keep}
    print(f"[{TRACK}] companies {len(by_comp):,} | total slugs {len(s2c):,} | "
          f"kept top3 {len(keep):,} | archived {len(arch):,}", flush=True)
    return top3


def init(top3):
    global TOP3
    TOP3 = top3


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
    ever = norm = jani = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            is_ever = is_norm = is_jani = False
            for e in exp if isinstance(exp, list) else []:
                if not isinstance(e, dict):
                    continue
                if role_slugs(e.get("company") or {}) & TOP3:
                    is_ever = True
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                    if present:
                        is_norm = True; is_jani = True
                    elif (not end) and start:
                        is_jani = True
            if is_ever:
                ever += 1
                norm += is_norm
                jani += is_jani
    return ever, norm, jani


def main():
    os.makedirs(C["out"], exist_ok=True)
    top3 = build_top3()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    EVER = NORM = JANI = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init, initargs=(top3,)) as pool:
        for ever, norm, jani in pool.imap_unordered(worker, shards):
            EVER += ever; NORM += norm; JANI += jani
    print(f"\n==== {TRACK.upper()} CONSOLIDATED (max 3 pages/company)  ({time.time()-t0:,.0f}s) ====")
    print(f"  ever worked (distinct profiles)      : {EVER:,}")
    print(f"  currently working - NORMAL (present) : {NORM:,}")
    print(f"  currently working - JANI (v2)        : {JANI:,}")


if __name__ == "__main__":
    main()
