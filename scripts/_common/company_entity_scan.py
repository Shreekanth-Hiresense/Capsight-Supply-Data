# Purpose: Over a track's CONNECTION-FILTERED shards (shards_min10conn), compute, using the consolidated
#   top-3 entity pages per company (top3_slugs.csv): per-COMPANY distinct ever / current-normal / current-
#   Jani (a person at >1 of the company's pages counts once), and per-ENTITY (slug) ever / current-normal /
#   current-Jani. Writes _company_totals.csv and _entity_counts.csv in the track folder. The Excel builder
#   then pivots these into one row per company. Read-only. Usage: TRACK=track1 python company_entity_scan.py
import ast, csv, glob, gzip, json, os, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve",
                   shards=os.path.join(r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles", os.environ.get("SHARD_SUB", "shards_min10conn")),
                   company_col="company"),
    "track2": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve",
                   shards=os.path.join(r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles", os.environ.get("SHARD_SUB", "shards_min10conn")),
                   company_col="company_target"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
C = CFG[TRACK]
FINAL = os.path.join(C["out"], "final_slugs.csv")   # ALL extracted entities (not top3, not dump discovery)
WORKERS = 15
S2C = None


def load_map():
    m = {}
    for r in csv.DictReader(open(FINAL, encoding="utf-8")):
        sl = (r.get("slug") or "").strip().lower()
        if sl:
            m[sl] = (r.get(C["company_col"]) or "").strip()
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


import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jani_rules import has_gcc_keyword, gated  # noqa: E402


def worker(path):
    se = Counter(); sn = Counter(); sj = Counter()      # per-slug ever/norm/jani
    ce = Counter(); cn = Counter(); cj = Counter()      # per-company ever/norm/jani
    te = tn = tj = 0                                     # overall distinct (per-profile)
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
            ev = set(); nm = set(); ja = set()
            for e in exp if isinstance(exp, list) else []:
                if not isinstance(e, dict):
                    continue
                for sl in (role_slugs(e.get("company") or {}) & keys):
                    ev.add(sl)
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                    if present:
                        nm.add(sl); ja.add(sl)
                    elif (not end) and start:
                        ja.add(sl)
            # EY/Deloitte: only credit their slugs if the profile has a GCC keyword
            if any(gated(S2C[s]) for s in ev):
                blob = " ".join(str(v) for v in row.values())
                if not has_gcc_keyword(blob):
                    ev = {s for s in ev if not gated(S2C[s])}
                    nm = {s for s in nm if not gated(S2C[s])}
                    ja = {s for s in ja if not gated(S2C[s])}
            for s in ev:
                se[s] += 1
            for s in nm:
                sn[s] += 1
            for s in ja:
                sj[s] += 1
            for comp in {S2C[s] for s in ev}:
                ce[comp] += 1
            for comp in {S2C[s] for s in nm}:
                cn[comp] += 1
            for comp in {S2C[s] for s in ja}:
                cj[comp] += 1
            if ev:
                te += 1
            if nm:
                tn += 1
            if ja:
                tj += 1
    return se, sn, sj, ce, cn, cj, te, tn, tj


def main():
    init()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    print(f"[{TRACK}] top3 slugs {len(S2C):,} | filtered shards {len(shards)} | workers {WORKERS}", flush=True)
    SE = Counter(); SN = Counter(); SJ = Counter(); CE = Counter(); CN = Counter(); CJ = Counter()
    TE = TN = TJ = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for se, sn, sj, ce, cn, cj, te, tn, tj in pool.imap_unordered(worker, shards):
            SE.update(se); SN.update(sn); SJ.update(sj); CE.update(ce); CN.update(cn); CJ.update(cj)
            TE += te; TN += tn; TJ += tj
    comps = set(S2C.values())
    with open(os.path.join(C["out"], "_company_totals.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company", "comp_ever", "comp_cur_normal", "comp_cur_jani"])
        for comp in sorted(comps, key=lambda c: -CJ.get(c, 0)):
            w.writerow([comp, CE.get(comp, 0), CN.get(comp, 0), CJ.get(comp, 0)])
    by_comp = defaultdict(list)
    for sl, comp in S2C.items():
        by_comp[comp].append(sl)
    with open(os.path.join(C["out"], "_entity_counts.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company", "slug", "linkedin_url", "ent_ever", "ent_cur_normal", "ent_cur_jani"])
        for comp in sorted(by_comp):
            for sl in sorted(by_comp[comp], key=lambda s: -SE.get(s, 0)):
                w.writerow([comp, sl, f"https://www.linkedin.com/company/{sl}/",
                            SE.get(sl, 0), SN.get(sl, 0), SJ.get(sl, 0)])
    print(f"\n[{TRACK}] OVERALL (distinct): ever {TE:,} | cur-normal {TN:,} | cur-jani {TJ:,}")
    print(f"[{TRACK}] done ({time.time()-t0:,.0f}s) | companies {len(comps)} -> _company_totals.csv, _entity_counts.csv")


if __name__ == "__main__":
    main()
