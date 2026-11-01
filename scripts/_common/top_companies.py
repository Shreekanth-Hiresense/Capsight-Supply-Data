# Purpose: Per-company headcount over a track's pulled shards (TRACK env). For each parent company, count
#   DISTINCT profiles who EVER worked there (any role at one of the company's slugs) and who are CURRENTLY
#   working there (NORMAL = duration.present ; JANI = present OR start-but-no-end). A profile that worked at
#   several companies is counted in each. Prints the top-N by overall headcount and writes a full CSV.
#   Usage: TRACK=track1 python top_companies.py   (or track2)
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jani_rules import has_gcc_keyword, gated, excluded  # noqa: E402  (single source of truth for rules)

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   company_col="company",
                   shards=os.environ.get("SHARD_DIR", r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"),
                   out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\top_companies_conn10.csv"),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   company_col="company_target",
                   shards=os.environ.get("SHARD_DIR", r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards"),
                   out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\top_companies_conn10.csv"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
C = CFG[TRACK]
WORKERS = 15
S2C = None


def load_map():
    m = {}
    for r in csv.DictReader(open(C["final"], encoding="utf-8")):
        sl = (r.get("slug") or "").strip().lower()
        comp = (r.get(C["company_col"]) or "").strip()
        if sl:
            m.setdefault(sl, comp)
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
    ever = Counter(); norm = Counter(); jani = Counter()
    te = tn = tj = 0
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
                for sl in (role_slugs(e.get("company") or {}) & S2C.keys()):
                    comp = S2C[sl]
                    ev.add(comp)
                    dur = e.get("duration") or {}
                    present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                    if present:
                        nm.add(comp); ja.add(comp)
                    elif (not end) and start:
                        ja.add(comp)
            # drop excluded companies (e.g. Sankalp) always
            ev = {c for c in ev if not excluded(c)}; nm = {c for c in nm if not excluded(c)}; ja = {c for c in ja if not excluded(c)}
            # GCC-keyword gate for EY/Deloitte: drop them unless a keyword appears in the profile
            if any(gated(c) for c in ev):
                blob = " ".join(str(v) for v in row.values())
                if not has_gcc_keyword(blob):
                    ev = {c for c in ev if not gated(c)}; nm = {c for c in nm if not gated(c)}; ja = {c for c in ja if not gated(c)}
            for c in ev:
                ever[c] += 1
            for c in nm:
                norm[c] += 1
            for c in ja:
                jani[c] += 1
            if ev:
                te += 1
            if nm:
                tn += 1
            if ja:
                tj += 1
    return ever, norm, jani, te, tn, tj


def main():
    init()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    print(f"[{TRACK}] companies {len(set(S2C.values())):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = Counter(); NORM = Counter(); JANI = Counter()
    TE = TN = TJ = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ev, nm, ja, te, tn, tj in pool.imap_unordered(worker, shards):
            EVER.update(ev); NORM.update(nm); JANI.update(ja); TE += te; TN += tn; TJ += tj
    with open(C["out"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company", "ever_worked", "currently_working_normal", "currently_working_jani"])
        for comp, n in EVER.most_common():
            w.writerow([comp, n, NORM.get(comp, 0), JANI.get(comp, 0)])
    print(f"\n==== {TRACK.upper()} OVERALL (distinct, this shard set) ====")
    print(f"  ever worked        : {TE:,}")
    print(f"  currently - normal : {TN:,}")
    print(f"  currently - jani   : {TJ:,}")
    print(f"\n==== {TRACK.upper()} TOP 10 COMPANIES (by currently-working jani)  ({time.time()-t0:,.0f}s) ====")
    print(f"  {'company':40s} {'ever':>10} {'cur-normal':>12} {'cur-jani':>10}")
    for comp, j in sorted(JANI.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {comp[:40]:40s} {EVER.get(comp,0):>10,} {NORM.get(comp,0):>12,} {j:>10,}")
    print(f"\n  full ranking -> {C['out']}")


if __name__ == "__main__":
    main()
