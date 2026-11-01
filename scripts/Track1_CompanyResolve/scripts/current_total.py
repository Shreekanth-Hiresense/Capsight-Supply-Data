# Purpose: Over the pulled Track-1 slug shards, count OVERALL ever-worked vs CURRENTLY-working (a role with
#   duration.present at a confirmed Track-1 slug). Uses the final (clean) slug set, so excluded/wrong slugs
#   don't count. Distinct people (one row per uid; uids disjoint across shards -> per-shard counts sum).
import ast, csv, glob, gzip, json, os, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"
SLUG_FILE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
WORKERS = 15
SLUGS = None


def init():
    global SLUGS
    SLUGS = {r["slug"].strip().lower() for r in csv.DictReader(open(SLUG_FILE, encoding="utf-8")) if r["slug"]}


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
    ever = cur = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            is_ever = is_cur = False
            for e in exp if isinstance(exp, list) else []:
                if not isinstance(e, dict):
                    continue
                if role_slugs(e.get("company") or {}) & SLUGS:
                    is_ever = True
                    if (e.get("duration") or {}).get("present"):
                        is_cur = True
                        break
            if is_ever:
                ever += 1
                if is_cur:
                    cur += 1
    return ever, cur


def main():
    init()
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"slugs {len(SLUGS):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = CUR = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ever, cur in pool.imap_unordered(worker, shards):
            EVER += ever
            CUR += cur
    print(f"\n==== TRACK-1 (slug-based) OVERALL ({time.time()-t0:,.0f}s) ====")
    print(f"  ever worked (distinct)   : {EVER:,}")
    print(f"  CURRENTLY working        : {CUR:,}")
    print(f"  past only                : {EVER-CUR:,}")


if __name__ == "__main__":
    main()
