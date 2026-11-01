# Purpose: For Deloitte / EY / PwC / KPMG, list EVERY entity page we included (all final_slugs entities,
#   not just the top 3) with its current headcount + LinkedIn URL. Counts over the FULL Track-1 pulled
#   shards: per-slug distinct ever / current-normal (present) / current-Jani (present or start-no-end).
#   Read-only. 10 workers (one job) to keep the terminal responsive.
import ast, csv, glob, gzip, json, os, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"
FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\big4_entities.csv"
WORKERS = 10
COMPANIES = {"deloitte", "ey", "pwc", "kpmg international"}
S2C = None


def load_map():
    m = {}
    for r in csv.DictReader(open(FINAL, encoding="utf-8")):
        comp = r["company"].strip().lower()
        if comp in COMPANIES:
            m[r["slug"].strip().lower()] = r["company"].strip()
    return m


def init():
    global S2C
    S2C = load_map()


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
    ev = Counter(); nm = Counter(); ja = Counter()
    keys = S2C.keys()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            e_ = set(); n_ = set(); j_ = set()
            for e in exp if isinstance(exp, list) else []:
                if not isinstance(e, dict):
                    continue
                for sl in (role_slugs(e.get("company") or {}) & keys):
                    e_.add(sl)
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                    if present:
                        n_.add(sl); j_.add(sl)
                    elif (not end) and start:
                        j_.add(sl)
            for s in e_:
                ev[s] += 1
            for s in n_:
                nm[s] += 1
            for s in j_:
                ja[s] += 1
    return ev, nm, ja


def main():
    init()
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"slugs {len(S2C)} across {len(set(S2C.values()))} companies | shards {len(shards)} | workers {WORKERS}", flush=True)
    EV = Counter(); NM = Counter(); JA = Counter()
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ev, nm, ja in pool.imap_unordered(worker, shards):
            EV.update(ev); NM.update(nm); JA.update(ja)
    by = defaultdict(list)
    for sl, comp in S2C.items():
        by[comp].append(sl)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company", "entity_slug", "linkedin_url", "ever_worked", "current_normal", "current_jani"])
        for comp in sorted(by):
            for sl in sorted(by[comp], key=lambda s: -EV.get(s, 0)):
                w.writerow([comp, sl, f"https://www.linkedin.com/company/{sl}/", EV.get(sl, 0), NM.get(sl, 0), JA.get(sl, 0)])
    print(f"\n==== BIG-4 ALL ENTITIES ({time.time()-t0:,.0f}s) -> big4_entities.csv ====")
    for comp in sorted(by):
        tot_e = sum(EV.get(s, 0) for s in by[comp]); tot_j = sum(JA.get(s, 0) for s in by[comp])
        print(f"\n{comp}  ({len(by[comp])} entities | sum ever {tot_e:,} | sum cur-jani {tot_j:,})")
        for sl in sorted(by[comp], key=lambda s: -EV.get(s, 0)):
            if EV.get(sl, 0) == 0:
                continue
            print(f"    {sl[:46]:46s} ever {EV.get(sl,0):>8,}  cur-normal {NM.get(sl,0):>7,}  cur-jani {JA.get(sl,0):>7,}")


if __name__ == "__main__":
    main()
