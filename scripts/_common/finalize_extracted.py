# Purpose: BAKE the curation rules into the extracted dataset (TRACK env). Rewrites each shard of
#   shards_min10conn in place, KEEPING a profile only if it still qualifies for >=1 company under the
#   full ruleset:
#     - a role at a slug that is in final_slugs (so Sankalp/hcltech, PwC-other-pages, Walmart-Canada,
#       pepsico-middleeast, Bosch, etc. - already removed from final_slugs - no longer qualify), AND
#     - for a GATED company (EY, Deloitte): the profile must also contain a GCC keyword anywhere.
#   A profile kept for ANY qualifying company stays (multi-company people are never lost). Profiles that
#   no longer qualify for anything are dropped from the extracted file. Rebuildable from the raw shards.
#   Usage: TRACK=track1 python finalize_extracted.py
import ast, csv, glob, gzip, json, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jani_rules import has_gcc_keyword, gated, excluded  # noqa: E402

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   company_col="company",
                   shards=os.path.join(r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles", os.environ.get("SHARD_SUB", "shards_min10conn"))),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   company_col="company_target",
                   shards=os.path.join(r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles", os.environ.get("SHARD_SUB", "shards_min10conn"))),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
C = CFG[TRACK]
WORKERS = 10
S2C = None


def load_map():
    m = {}
    for r in csv.DictReader(open(C["final"], encoding="utf-8")):
        sl = (r.get("slug") or "").strip().lower()
        comp = (r.get(C["company_col"]) or "").strip()
        if sl and not excluded(comp):
            m[sl] = comp
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


def qualifies(row):
    try:
        exp = ast.literal_eval(row.get("experience") or "[]")
    except Exception:
        try:
            exp = json.loads(row.get("experience") or "[]")
        except Exception:
            exp = []
    comps = set()
    for e in exp if isinstance(exp, list) else []:
        if not isinstance(e, dict):
            continue
        for sl in (role_slugs(e.get("company") or {}) & S2C.keys()):
            comps.add(S2C[sl])
    if not comps:
        return False
    # non-gated company present -> keep
    if any(not gated(c) for c in comps):
        return True
    # only gated (EY/Deloitte) companies -> require GCC keyword
    blob = " ".join(str(v) for v in row.values())
    return has_gcc_keyword(blob)


def rewrite(path):
    tmp = path + ".tmp"
    kept = removed = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        gz = gzip.open(tmp, "wt", encoding="utf-8", newline="")
        w = csv.DictWriter(gz, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rd:
            if qualifies(row):
                w.writerow(row); kept += 1
            else:
                removed += 1
        gz.close()
    os.replace(tmp, path)
    return kept, removed


def main():
    init()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    print(f"[{TRACK}] final slugs {len(S2C):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    K = R = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for kept, removed in pool.imap_unordered(rewrite, shards):
            K += kept; R += removed
    print(f"\n==== {TRACK.upper()} extracted set finalized ({time.time()-t0:,.0f}s) ====")
    print(f"  kept    : {K:,}")
    print(f"  removed : {R:,}  (no longer qualify under the ruleset)")


if __name__ == "__main__":
    main()
