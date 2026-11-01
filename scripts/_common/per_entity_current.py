# Purpose: Per-ENTITY-PAGE (per-slug) headcount for the retained top-3 pages of each company (TRACK env).
#   For every slug in top3_slugs.csv, count DISTINCT profiles: ever worked, currently working NORMAL
#   (duration.present) and JANI (present OR start-but-no-end), by scanning the pulled shards. Writes
#   top3_entity_current.csv (company, slug, ever, cur_normal, cur_jani) and prints the per-entity rows for
#   the top companies. Usage: TRACK=track1 python per_entity_current.py   (or track2)
import ast, csv, glob, gzip, json, os, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve",
                   shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"),
    "track2": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve",
                   shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
C = CFG[TRACK]
TOP3_CSV = os.path.join(C["out"], "top3_slugs.csv")
WORKERS = 15
KEEP = None


def load_keep():
    keep = {}
    for r in csv.DictReader(open(TOP3_CSV, encoding="utf-8")):
        keep[r["slug"].strip().lower()] = r["company"]
    return keep


def init():
    global KEEP
    KEEP = load_keep()


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
    ever = Counter(); norm = Counter(); jani = Counter()
    keepset = KEEP.keys()
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
                for sl in (role_slugs(e.get("company") or {}) & keepset):
                    ev.add(sl)
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                    if present:
                        nm.add(sl); ja.add(sl)
                    elif (not end) and start:
                        ja.add(sl)
            for s in ev:
                ever[s] += 1
            for s in nm:
                norm[s] += 1
            for s in ja:
                jani[s] += 1
    return ever, norm, jani


def main():
    init()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    print(f"[{TRACK}] top3 slugs {len(KEEP):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = Counter(); NORM = Counter(); JANI = Counter()
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ev, nm, ja in pool.imap_unordered(worker, shards):
            EVER.update(ev); NORM.update(nm); JANI.update(ja)
    # group by company
    by_comp = defaultdict(list)
    for sl, comp in KEEP.items():
        by_comp[comp].append(sl)
    out = os.path.join(C["out"], "top3_entity_current.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company", "slug", "ever_worked", "currently_working_normal", "currently_working_jani"])
        # order companies by total ever desc
        comp_total = {c: sum(EVER.get(s, 0) for s in sls) for c, sls in by_comp.items()}
        for comp in sorted(by_comp, key=lambda c: -comp_total[c]):
            for sl in sorted(by_comp[comp], key=lambda s: -EVER.get(s, 0)):
                w.writerow([comp, sl, EVER.get(sl, 0), NORM.get(sl, 0), JANI.get(sl, 0)])
    # print top 12 companies with their entity rows
    comp_total = {c: sum(EVER.get(s, 0) for s in sls) for c, sls in by_comp.items()}
    print(f"\n==== {TRACK.upper()} per-entity currently-working (top companies)  ({time.time()-t0:,.0f}s) ====")
    for comp in sorted(by_comp, key=lambda c: -comp_total[c])[:12]:
        print(f"\n{comp}  (company total ever {comp_total[comp]:,})")
        for sl in sorted(by_comp[comp], key=lambda s: -EVER.get(s, 0)):
            print(f"    {sl[:42]:42s} ever {EVER.get(sl,0):>8,}  cur-normal {NORM.get(sl,0):>8,}  cur-jani {JANI.get(sl,0):>8,}")
    print(f"\n  full -> {out}")


if __name__ == "__main__":
    main()
