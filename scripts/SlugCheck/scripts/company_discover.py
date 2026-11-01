# Purpose: Discover the LinkedIn page slugs (entities) for a company name from the dump (read-only). For
#   every experience role whose company.name contains NAME (env, lowercased substring), tally per SLUG:
#   distinct profiles (ever), currently working (Jani = present or start-no-end), an example name, domain.
#   Prints slugs sorted by ever with the LinkedIn URL. Use for a company not yet pulled.
#   Usage: NAME=millennium PRE=millennium python company_discover.py
import glob, gzip, os, sys, time
from collections import defaultdict
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
NAME = os.environ.get("NAME", "").lower()
PRE = os.environ.get("PRE", NAME).lower().encode()
WORKERS = 12
MIN_SHOW = int(os.environ.get("MIN_SHOW", "10"))
if not NAME:
    sys.exit("set NAME=")


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
    ever = defaultdict(set); cur = defaultdict(set); ex = {}; dom = {}
    with gzip.open(path, "rb") as f:
        for line in f:
            if PRE not in line.lower():
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            for e in d.get("experience") or []:
                c = e.get("company") or {}
                nm = (c.get("name") or "")
                if NAME not in nm.lower():
                    continue
                sl = slug_of(c)
                if not sl:
                    sl = "(no-slug)"
                ever[sl].add(uid)
                ex.setdefault(sl, nm); dom.setdefault(sl, (c.get("domain") or ""))
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    cur[sl].add(uid)
    return {k: (v, cur.get(k, set()), ex.get(k, ""), dom.get(k, "")) for k, v in ever.items()}


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"NAME='{NAME}' | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = defaultdict(set); CUR = defaultdict(set); EX = {}; DOM = {}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for res in pool.imap_unordered(worker, shards):
            for sl, (ev, cu, exn, dm) in res.items():
                EVER[sl] |= ev; CUR[sl] |= cu; EX.setdefault(sl, exn); DOM.setdefault(sl, dm)
    allu = set()
    for v in EVER.values():
        allu |= v
    print(f"\n==== '{NAME}' pages ({time.time()-t0:,.0f}s) | total distinct profiles (any such page): {len(allu):,} ====")
    rows = sorted(EVER.items(), key=lambda kv: -len(kv[1]))
    for sl, uids in rows:
        if len(uids) < MIN_SHOW:
            continue
        url = ("https://www.linkedin.com/company/" + sl + "/") if sl != "(no-slug)" else "(no slug)"
        print(f"  {len(uids):>7,} ever | {len(CUR.get(sl,())):>6,} cur-jani | {sl[:40]:40s} | {url}")
        print(f"          ex='{EX.get(sl,'')[:40]}' dom={DOM.get(sl,'')}")


if __name__ == "__main__":
    main()
