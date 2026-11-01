# Purpose: For given company SLUG(s), over the WHOLE passive_IN dump (read-only), break down how each
#   matched role's duration is recorded, and report "currently working" under THREE definitions so the
#   user can choose. A role at the target slug is classified by its duration dict:
#     present  = duration.present is true                         -> clearly current
#     ended    = duration.end is set (a stop date is given)       -> clearly past
#     no_start_no_end = not present, no end, AND no start         -> neither start nor stop mentioned
#     start_no_end    = not present, no end, but a start is given -> started, no stop mentioned
#   Per distinct profile (uid) we aggregate its roles at the slug, then count:
#     STRICT  current = has a 'present' role                      (existing logic)
#     USER    current = STRICT  OR has a 'no_start_no_end' role   (neither start nor stop mentioned)
#     BROAD   current = STRICT  OR has ANY role without an end    (no stop date = assume still ongoing)
#   Usage: SLUGS="lpl-financial,lpl-global-capability-center" python slug_current_variants.py
import glob, gzip, os, sys, time
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
TARGETS = tuple(s.strip().lower() for s in os.environ.get("SLUGS", "").split(",") if s.strip())
PREFILTERS = tuple(s.encode() for s in TARGETS)
WORKERS = 15
if not TARGETS:
    sys.exit("set SLUGS env")


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    return (u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()) or None


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


def classify(dur):
    present = bool(dur.get("present"))
    end = dur.get("end")
    start = dur.get("start")
    if present:
        return "present"
    if end:
        return "ended"
    return "no_start_no_end" if not start else "start_no_end"


def worker(path):
    # per slug: uid -> set of role-classes that uid has at that slug
    res = {t: {} for t in TARGETS}
    tset = set(TARGETS)
    with gzip.open(path, "rb") as f:
        for line in f:
            low = line.lower()
            if not any(p in low for p in PREFILTERS):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            for e in d.get("experience") or []:
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & tset
                if not hit:
                    continue
                cls = classify(e.get("duration") or {})
                for t in hit:
                    res[t].setdefault(uid, set()).add(cls)
    return res


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"slugs={list(TARGETS)}  shards={len(shards)}  workers={WORKERS}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, shards), 1):
            for t, d in res.items():
                for uid, classes in d.items():
                    merged[t].setdefault(uid, set()).update(classes)
            if i % 50 == 0:
                print(f"  {i}/{len(shards)} ({time.time()-t0:,.0f}s)", flush=True)
    print(f"\n==== CURRENT-WORKING VARIANTS (whole passive_IN dump)  ({time.time()-t0:,.0f}s) ====")
    for t in TARGETS:
        d = merged[t]
        ever = len(d)
        strict = sum(1 for c in d.values() if "present" in c)
        v1 = sum(1 for c in d.values() if ("present" in c) or ("no_start_no_end" in c))
        v2 = sum(1 for c in d.values() if ("present" in c) or ("start_no_end" in c))
        broad = sum(1 for c in d.values() if c & {"present", "no_start_no_end", "start_no_end"})
        print(f"\n  {t}:  ever worked (distinct) = {ever:,}")
        print(f"    NORMAL current  (duration.present only)                   : {strict:,}")
        print(f"    V1     current  (present + neither start nor stop given)   : {v1:,}   (+{v1-strict:,})")
        print(f"    V2     current  (present + start given but no end date)    : {v2:,}   (+{v2-strict:,})")
        print(f"    BROAD  current  (present + any role with no end date)      : {broad:,}   (+{broad-strict:,})")


if __name__ == "__main__":
    main()
