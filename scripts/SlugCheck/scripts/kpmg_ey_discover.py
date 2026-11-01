# Purpose: Discover the REAL LinkedIn page slugs for KPMG and EY (incl. India / GDS) from the whole dump,
#   instead of guessing. Prefilter lines mentioning kpmg / ernst (Ernst & Young) / EY GDS phrases, then for
#   each matching role tally per-SLUG: distinct profiles (ever) and currently working (Jani = present or
#   start-no-end). Prints slugs sorted by ever, with an example name. Read-only. 12 workers, one job.
import glob, gzip, os, time
from collections import defaultdict
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
WORKERS = 12
PRE = (b"kpmg", b"ernst", b"eygds", b"eygbs", b"ey gds", b"ey-gds", b"global delivery services")
NAME_HINTS = ("kpmg", "ernst", "ey gds", "ey global", "eygds", "eygbs", "ey india", "global delivery services")


def slug_of(c):
    uid = c.get("lnkd_uid")
    if uid:
        return str(uid).strip().lower()
    for k in ("lnkd_url1", "lnkd_url2"):
        u = c.get(k)
        if u and "/company/" in u:
            s = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s:
                return s
    return ""


def worker(path):
    ever = defaultdict(set); cur = defaultdict(set); ex = {}
    with gzip.open(path, "rb") as f:
        for line in f:
            low = line.lower()
            if not any(p in low for p in PRE):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            for e in d.get("experience") or []:
                comp = e.get("company") or {}
                nm = (comp.get("name") or "").lower()
                if not any(h in nm for h in NAME_HINTS):
                    continue
                sl = slug_of(comp)
                if not sl:
                    continue
                ever[sl].add(uid)
                ex.setdefault(sl, comp.get("name") or "")
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    cur[sl].add(uid)
    return {k: (v, cur.get(k, set()), ex.get(k, "")) for k, v in ever.items()}


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = defaultdict(set); CUR = defaultdict(set); EX = {}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for res in pool.imap_unordered(worker, shards):
            for sl, (ev, cu, exn) in res.items():
                EVER[sl] |= ev; CUR[sl] |= cu; EX.setdefault(sl, exn)
    print(f"\n==== KPMG / EY page slugs discovered ({time.time()-t0:,.0f}s) ====")
    rows = sorted(EVER.items(), key=lambda kv: -len(kv[1]))
    for sl, uids in rows:
        if len(uids) < 20:
            continue
        print(f"  {sl[:46]:46s} ever {len(uids):>7,}  cur-jani {len(CUR.get(sl,())):>7,}  ex='{EX.get(sl,'')[:30]}'")


if __name__ == "__main__":
    main()
