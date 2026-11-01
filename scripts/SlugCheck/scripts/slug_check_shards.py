# Purpose: Generic LinkedIn-company SLUG check over a folder of CSV.GZ shards (e.g. the Track-1 3.9M set).
#   SHARDS env = shard dir; SLUGS env = comma-separated company slugs. Match experience company by slug
#   (lnkd_uid or /company/<slug> in lnkd_url1/url2). Report present?, distinct ever-worked, currently-working
#   (duration.present) vs past. Usage: SHARDS="...\shards" SLUGS="jpmorganchase" python slug_check_shards.py
import ast, csv, glob, gzip, json, os, sys, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = os.environ.get("SHARDS", r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_Companies_profiles\shards")
TARGETS = tuple(s.strip().lower() for s in os.environ.get("SLUGS", "").split(",") if s.strip())
WORKERS = 15
if not TARGETS:
    sys.exit("set SLUGS env")


def slug_from_url(u):
    if not u:
        return None
    for marker in ("/company/", "/showcase/"):   # handle both company and showcase URLs
        if marker in u:
            return (u.rstrip("/").split(marker)[-1].split("/")[0].strip().lower()) or None
    return None


def role_slugs(company):
    s = set()
    uid = company.get("lnkd_uid")
    if uid:
        s.add(str(uid).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        sl = slug_from_url(company.get(k))
        if sl:
            s.add(sl)
    return s


def parse_exp(cell):
    if not cell:
        return []
    try:
        v = ast.literal_eval(cell)
    except Exception:
        try:
            v = json.loads(cell)
        except Exception:
            return []
    return v if isinstance(v, list) else []


def worker(path):
    res = {t: {} for t in TARGETS}
    tset = set(TARGETS)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cell = row.get("experience") or ""
            low = cell.lower()
            if not any(t in low for t in TARGETS):
                continue
            uid = row.get("uid")
            for e in parse_exp(cell):
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & tset
                if not hit:
                    continue
                present = bool((e.get("duration") or {}).get("present"))
                for t in hit:
                    res[t][uid] = res[t].get(uid, False) or present
    return res


def main():
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"slugs={list(TARGETS)}  shards={len(shards)} in {SHARD_DIR}  workers={WORKERS}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, shards), 1):
            for t, d in res.items():
                for uid, pres in d.items():
                    merged[t][uid] = merged[t].get(uid, False) or pres
    print(f"\n==== SLUG CHECK on shards  ({time.time()-t0:,.0f}s) ====")
    for t in TARGETS:
        d = merged[t]; total = len(d); cur = sum(1 for v in d.values() if v)
        print(f"\n  {t}:  {'PRESENT' if total else 'NOT FOUND'}")
        print(f"    distinct profiles (ever worked) : {total:,}")
        print(f"    currently working               : {cur:,}")
        print(f"    worked in the past (not current): {total-cur:,}")


if __name__ == "__main__":
    main()
