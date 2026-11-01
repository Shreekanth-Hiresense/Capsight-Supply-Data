# Purpose: Over the pulled Track-2 slug shards, count OVERALL distinct profiles: ever worked, currently
#   working NORMAL (duration.present only), and currently working JANI (present OR a role with a start
#   date but no end date), considering only roles at a confirmed Track-2 slug (final_slugs.csv). One row
#   per uid; uids are disjoint across shards (the two passive_IN folders don't overlap) so per-shard counts sum.
import ast, csv, glob, gzip, json, os, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards"
SLUG_FILE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv"
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
                if role_slugs(e.get("company") or {}) & SLUGS:
                    is_ever = True
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present"))
                    end = dur.get("end")
                    start = dur.get("start")
                    if present:
                        is_norm = True; is_jani = True
                    elif (not end) and start:
                        is_jani = True
            if is_ever:
                ever += 1
                if is_norm:
                    norm += 1
                if is_jani:
                    jani += 1
    return ever, norm, jani


def main():
    init()
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"slugs {len(SLUGS):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = NORM = JANI = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ever, norm, jani in pool.imap_unordered(worker, shards):
            EVER += ever; NORM += norm; JANI += jani
    print(f"\n==== TRACK-2 OVERALL ({time.time()-t0:,.0f}s) ====")
    print(f"  ever worked (distinct profiles)      : {EVER:,}")
    print(f"  currently working - NORMAL (present) : {NORM:,}")
    print(f"  currently working - JANI (v2)        : {JANI:,}")
    print(f"  past only (JANI)                     : {EVER-JANI:,}")


if __name__ == "__main__":
    main()
