# Purpose: Discover LinkedIn page slugs (entities) for SEVERAL company names in one dump pass (read-only).
#   NAMES env = comma-separated lowercased substrings (e.g. "pepsico,mercedes,walmart"). For each experience
#   role, assign it to the FIRST NAME that is a substring of company.name; tally per (name, slug): distinct
#   profiles (ever), currently working (Jani = present or start-no-end), example name, domain. Prints each
#   company's entity pages with URL, ever, cur-jani. Usage: NAMES="pepsico,mercedes,walmart" python ...
import glob, gzip, os, sys, time
from collections import defaultdict
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
NAMES = [n.strip().lower() for n in os.environ.get("NAMES", "").split(",") if n.strip()]
WORKERS = 12
MIN_SHOW = int(os.environ.get("MIN_SHOW", "20"))
if not NAMES:
    sys.exit("set NAMES=a,b,c")
PRE = tuple(n.encode() for n in NAMES)


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
    return "(no-slug)"


def worker(path):
    ever = {}; cur = {}; ex = {}; dom = {}
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
                c = e.get("company") or {}
                nm = (c.get("name") or "").lower()
                tgt = next((n for n in NAMES if n in nm), None)
                if not tgt:
                    continue
                sl = slug_of(c)
                ever.setdefault(tgt, {}).setdefault(sl, set()).add(uid)
                ex.setdefault(tgt, {}).setdefault(sl, c.get("name") or "")
                dom.setdefault(tgt, {}).setdefault(sl, c.get("domain") or "")
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    cur.setdefault(tgt, {}).setdefault(sl, set()).add(uid)
    return ever, cur, ex, dom


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"NAMES={NAMES} | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = defaultdict(lambda: defaultdict(set)); CUR = defaultdict(lambda: defaultdict(set))
    EX = defaultdict(dict); DOM = defaultdict(dict)
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for ever, cur, ex, dom in pool.imap_unordered(worker, shards):
            for t in ever:
                for sl, s in ever[t].items():
                    EVER[t][sl] |= s
                for sl, s in cur.get(t, {}).items():
                    CUR[t][sl] |= s
                for sl, v in ex.get(t, {}).items():
                    EX[t].setdefault(sl, v)
                for sl, v in dom.get(t, {}).items():
                    DOM[t].setdefault(sl, v)
    for t in NAMES:
        allu = set()
        for s in EVER[t].values():
            allu |= s
        print(f"\n===================== '{t}'  (total distinct profiles: {len(allu):,}) =====================")
        for sl, uids in sorted(EVER[t].items(), key=lambda kv: -len(kv[1])):
            if len(uids) < MIN_SHOW:
                continue
            url = ("https://www.linkedin.com/company/" + sl + "/") if sl != "(no-slug)" else "(no slug)"
            print(f"  {len(uids):>7,} ever | {len(CUR[t].get(sl,())):>6,} cur-jani | {sl[:42]:42s} | {url}")
            print(f"          ex='{EX[t].get(sl,'')[:42]}' dom={DOM[t].get(sl,'')}")
    print(f"\n({time.time()-t0:,.0f}s)")


if __name__ == "__main__":
    main()
