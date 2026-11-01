# Purpose: Generic LinkedIn-company SLUG check over the WHOLE passive_IN dump (both ziplabs_passive_IN_*
#   folders, read-only). Given one or more company slugs (SLUGS env, comma-separated; e.g. the segment
#   after /company/ in a LinkedIn URL), find profiles with an experience role at that exact company entity
#   (matched by company.lnkd_uid OR the /company/<slug> segment of lnkd_url1/url2 - NOT by display name),
#   and report: present?, distinct profiles, currently-working (duration.present) vs past. 15-worker scan.
#   Usage: SLUGS="jpmorganchase" python slug_check_dump.py
import glob, gzip, os, sys, time
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
TARGETS = tuple(s.strip().lower() for s in os.environ.get("SLUGS", "").split(",") if s.strip())
PREFILTERS = tuple(s.encode() for s in TARGETS)
WORKERS = 15
if not TARGETS:
    sys.exit("set SLUGS env, e.g. SLUGS=jpmorganchase")


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


def worker(path):
    res = {t: {} for t in TARGETS}   # slug -> {uid: present_any}
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
                hit = role_slugs(e.get("company") or {}) & set(TARGETS)
                if not hit:
                    continue
                present = bool((e.get("duration") or {}).get("present"))
                for t in hit:
                    res[t][uid] = res[t].get(uid, False) or present
    return res


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"slugs={list(TARGETS)}  pools={[os.path.basename(p) for p in POOLS]}  shards={len(shards)}  workers={WORKERS}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, shards), 1):
            for t, d in res.items():
                for uid, pres in d.items():
                    merged[t][uid] = merged[t].get(uid, False) or pres
            if i % 25 == 0:
                print(f"  {i}/{len(shards)} ({time.time()-t0:,.0f}s)", flush=True)
    print(f"\n==== SLUG CHECK (whole passive_IN dump)  ({time.time()-t0:,.0f}s) ====")
    allu, allc = set(), set()
    for t in TARGETS:
        d = merged[t]; total = len(d); cur = sum(1 for v in d.values() if v)
        allu |= set(d); allc |= {u for u, v in d.items() if v}
        print(f"\n  {t}:  {'PRESENT' if total else 'NOT FOUND'}")
        print(f"    distinct profiles (ever worked) : {total:,}")
        print(f"    currently working               : {cur:,}")
        print(f"    worked in the past (not current): {total-cur:,}")
    if len(TARGETS) > 1:
        print(f"\n  COMBINED distinct: ever {len(allu):,} | current {len(allc):,} | past {len(allu)-len(allc):,}")


if __name__ == "__main__":
    main()
