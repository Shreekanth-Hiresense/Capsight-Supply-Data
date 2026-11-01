# Purpose: Track-2 Part-2 under the NEW rule (user 2026-10-29): REPLACE the column-B domestic-role negation
#   with the Capsight 11-function filter. Keep the other standing company rules (EXCLUDES = IBM/HP/People
#   Tech/NTT/Bosch + Track-1/Track-2 overlaps; per-company LOC_ONLY = Teleperformance/Siemens/Philips; drop
#   interns; >=20 conn). NO Maruti-style location filter (that was Maruti-only).
#   Produces, over the Part-2 pulled shards (one row per uid, disjoint across shards -> per-shard counts sum):
#     * OVERALL ever-worked distinct (NO function filter)                         -> count
#     * CURRENTLY-working (Jani) -> classify whole profile via GCC taxonomy ->
#       KEEP only the 11 functions -> filtered CSV (32 original cols) + breakdown by function & company.
#   Read-only on the dump/shards. 12 workers. Writes outputs to the Part-2 folder / Jani Capsight.
import ast, csv, glob, gzip, json, os, shutil, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

P2DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts"
sys.path.insert(0, P2DIR)
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
import gcc_taxonomy_classifier as TC

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(2 ** 31 - 1)
FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv"
SHARDS = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards"
T1 = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
T2 = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_current_11functions.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\p2_parts"
WORKERS = 12
S2C = None; EXCL = None; COMP = None; COLS = None


def init():
    global S2C, EXCL, COMP
    S2C = {}
    rows = list(csv.DictReader(open(FINAL, encoding="utf-8")))
    for r in rows:
        sl = (r.get("slug") or "").strip().lower()
        if sl:
            S2C[sl] = (r.get("company_target") or "").strip()
    EXCL = {P2.cnorm(x) for x in P2.EXCLUDE_P2}
    for f, col in ((T1, "company"), (T2, "company_target")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get(col):
                EXCL.add(P2.cnorm(r[col]))
    COMP = TC.load()


# the 32 original profile columns we export (the shards already carry them)
def shard_cols(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def role_slugs(c):
    s = set()
    if c.get("lnkd_uid"):
        s.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        u = c.get(k)
        if u and "/company/" in u:
            sl = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if sl:
                s.add(sl)
    return s


def parse(x):
    try:
        v = ast.literal_eval(x or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def worker(path):
    ever = 0; ever_co = Counter(); ever_slug = Counter()
    cur_kept = 0; func = Counter(); func_co = Counter(); func_slug = Counter(); how = Counter()
    outp = os.path.join(TMP, os.path.basename(path) + ".csv")
    fo = open(outp, "w", encoding="utf-8", newline="")
    w = csv.writer(fo, quoting=csv.QUOTE_ALL)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames                     # the shard's 32 ORIGINAL columns
        for row in rd:
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            exp = parse(row.get("experience"))
            loc_text = ((row.get("miniprofile_location_address") or "") + " "
                        + (row.get("miniprofile_location_region") or "")).lower()
            # gather per-company: slugs, titles, current flag  (roles at Part-2 slugs)
            cslug = defaultdict(set); ctitle = defaultdict(list); ccur = defaultdict(bool)
            cur_title = ""; past = []; descs = []
            for e in exp:
                if not isinstance(e, dict):
                    continue
                t = e.get("title") or ""
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if is_cur and not cur_title:
                    cur_title = t
                else:
                    past.append(t)
                if e.get("description"):
                    descs.append(str(e.get("description")))
                hit = role_slugs(e.get("company") or {}) & S2C.keys()
                if not hit:
                    continue
                for comp in {S2C[s] for s in hit}:
                    ctitle[comp].append(t)
                    if is_cur:
                        ccur[comp] = True
                for s in hit:
                    cslug[S2C[s]].add(s)
            # which companies qualify (standing rules, NO CAT negation)
            ever_hit = False; cur_hit = False; cur_companies = []; cur_slugs = set()
            for comp, sls in cslug.items():
                cl = comp.strip().lower()
                if cl in P2.EXCLUDE_P2 or P2.cnorm(comp) in EXCL:
                    continue
                allowed = P2.LOC_ONLY_P2.get(cl)
                if allowed is not None and not any(tok in loc_text for tok in allowed):
                    continue
                if P2.INTERN.search(" ; ".join(ctitle[comp])):
                    continue
                ever_hit = True; ever_co[comp] += 1
                for s in sls:
                    ever_slug[s] += 1
                if ccur.get(comp):
                    cur_hit = True; cur_companies.append(comp); cur_slugs |= sls
            if ever_hit:
                ever += 1
            if cur_hit:
                skills = parse(row.get("skill"))
                sk = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
                res = TC.classify(row.get("miniprofile_headline"), cur_title, sk, " ; ".join(past),
                                  row.get("miniprofile_summary"), " ".join(descs), COMP)
                b = TC.map_to_user11(res["L1"], res["L2"], res["L3_Role"])
                if b:
                    cur_kept += 1; func[b] += 1; how[res["how"]] += 1
                    for comp in cur_companies:
                        func_co[comp] += 1
                    for s in cur_slugs:
                        func_slug[s] += 1
                    w.writerow([row.get(c, "") for c in cols])
    fo.close()
    return outp, ever, cur_kept, ever_co, func, func_co, how, ever_slug, func_slug


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    init()
    shards = sorted(glob.glob(os.path.join(SHARDS, "*.csv.gz")))
    _lim = os.environ.get("LIMIT_FILES")
    if _lim:
        shards = shards[:int(_lim)]
    cols = shard_cols(shards[0])                  # 32 original profile columns from the shards
    print(f"Part-2 shards {len(shards)} | slugs {len(S2C)} | excl-companies {len(EXCL)} | workers {WORKERS}",
          flush=True)
    parts = []; EVER = 0; CUR = 0; EVERCO = Counter(); FUNC = Counter(); FUNCCO = Counter(); HOW = Counter()
    EVERSLUG = Counter(); FUNCSLUG = Counter()
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for outp, ever, cur, ec, fn, fco, how, es, fs in pool.imap_unordered(worker, shards):
            parts.append(outp); EVER += ever; CUR += cur
            EVERCO.update(ec); FUNC.update(fn); FUNCCO.update(fco); HOW.update(how)
            EVERSLUG.update(es); FUNCSLUG.update(fs)
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols)
        n = 0
        for p in sorted(parts):
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for line in fi:
                    fo.write(line); n += 1
    shutil.rmtree(TMP, ignore_errors=True)
    # save per-company breakdown
    cob = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_current_11functions_by_company.csv"
    with open(cob, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "ever_worked", "current_in_11"])
        for comp in sorted(EVERCO, key=lambda c: -EVERCO[c]):
            w.writerow([comp, EVERCO[comp], FUNCCO.get(comp, 0)])
    # per-entity breakdown
    slug2co = {s: c for s, c in S2C.items()}
    eob = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_current_11functions_by_entity.csv"
    with open(eob, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["entity_slug", "company", "linkedin_url", "ever_worked", "current_in_11"])
        for s in sorted(EVERSLUG, key=lambda x: -EVERSLUG[x]):
            w.writerow([s, slug2co.get(s, ""), f"https://www.linkedin.com/company/{s}/",
                        EVERSLUG[s], FUNCSLUG.get(s, 0)])
    print(f"\n==== Part-2 DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  OVERALL ever-worked distinct (no function filter): {EVER:,}")
    print(f"  CURRENTLY-working (Jani) kept in the 11 functions : {CUR:,}  (matched via {dict(HOW)})")
    print(f"\n  current-in-11 by function:")
    for b in TC.USER_11:
        print(f"    {b:38s} {FUNC.get(b,0):>7,}")
    print(f"\n  TOP 20 companies by currently-working-in-11:")
    for comp, _ in FUNCCO.most_common(20):
        print(f"    {comp[:34]:34s} ever {EVERCO.get(comp,0):>7,} | cur-in-11 {FUNCCO[comp]:>7,}")
    print(f"\n  TOP 20 entities (slugs) by currently-working-in-11:")
    for s, _ in FUNCSLUG.most_common(20):
        print(f"    {s[:34]:34s} ever {EVERSLUG.get(s,0):>7,} | cur-in-11 {FUNCSLUG[s]:>7,}")
    print(f"\n  -> filtered CSV: {OUT}  ({len(cols)} cols)")
    print(f"  -> per-company:  {cob}")
    print(f"  -> per-entity:   {eob}")


if __name__ == "__main__":
    main()
