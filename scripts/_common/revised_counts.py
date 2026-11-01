# Purpose: Revised per-company / per-entity / overall counts on the >=20 extracted set (TRACK env),
#   applying ALL standing rules PLUS new company-specific gates (credited at attribution time; multi-company
#   people are never deleted, just not credited to a company they fail the gate for):
#     - EY / Deloitte : profile must have a GCC keyword (jani_rules)
#     - Microsoft, Google, Amazon : profile connections >= 35
#     - Amazon (only) : location in {hyd, bengaluru, mumbai, chennai, delhi-NCR, coimbatore, pune}
#       (profile address/region OR an Amazon role's location) AND the person's CURRENT Amazon role is NOT a
#       generic domestic-sales role.
#   Writes _company_totals_revised.csv / _entity_counts_revised.csv and prints overall + top-10 w/ entities.
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jani_rules import has_gcc_keyword, gated  # noqa: E402

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve",
                   shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn",
                   company_col="company"),
    "track2": dict(out=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve",
                   shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn",
                   company_col="company_target"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
C = CFG[TRACK]
FINAL = os.path.join(C["out"], "final_slugs.csv")
WORKERS = 12
CONN35 = {"microsoft", "google", "amazon"}
HUBS = ["hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai", "navi mumbai", "thane",
        "chennai", "delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad",
        "coimbatore", "pune"]
SALES = re.compile(r"\b(sales|business development|account manager|account executive|territory|"
                   r"relationship manager|field sales|inside sales|channel sales|sales development|"
                   r"area sales|regional sales|sales executive|sales associate|sales officer)\b", re.I)
VIZAG = ["visakhapatnam", "vishakhapatnam", "vishakapatnam", "vizag", "vskp", "vysac"]
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


def hub(text):
    t = (text or "").lower()
    return any(h in t for h in HUBS)


def amazon_ok(row, exp, prof_hub):
    # location: profile hub OR any amazon-company role location is a hub
    loc_ok = prof_hub
    cur_sales = False
    for e in exp:
        if not isinstance(e, dict):
            continue
        sls = role_slugs(e.get("company") or {}) & S2C.keys()
        if not any(S2C[s].lower() == "amazon" for s in sls):
            continue
        if not loc_ok and hub(e.get("location") or ""):
            loc_ok = True
        dur = e.get("duration") or {}
        is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
        if is_cur and SALES.search(e.get("title") or ""):
            cur_sales = True
    return loc_ok and not cur_sales


def ntt_vizag_ok(row, exp):
    prof = ((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower()
    if any(v in prof for v in VIZAG):
        return True
    for e in exp:
        if not isinstance(e, dict):
            continue
        if any(S2C.get(s, "").lower() == "ntt data group" for s in (role_slugs(e.get("company") or {}) & S2C.keys())):
            if any(v in (e.get("location") or "").lower() for v in VIZAG):
                return True
    return False


def worker(path):
    se = Counter(); sn = Counter(); sj = Counter()
    ce = Counter(); cn = Counter(); cj = Counter()
    te = tn = tj = 0
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
            if not isinstance(exp, list):
                exp = []
            # per-slug ever/norm/jani
            ev = set(); nm = set(); ja = set()
            for e in exp:
                if not isinstance(e, dict):
                    continue
                for sl in (role_slugs(e.get("company") or {}) & keys):
                    ev.add(sl)
                    dur = e.get("duration") or {}
                    if bool(dur.get("present")):
                        nm.add(sl); ja.add(sl)
                    elif (not dur.get("end")) and dur.get("start"):
                        ja.add(sl)
            if not ev:
                continue
            comps = {S2C[s] for s in ev}
            # ---- gates (drop a company's slugs from this profile's credit if it fails) ----
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            blob = None
            prof_hub = hub((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or ""))
            drop_companies = set()
            for comp in comps:
                cl = comp.lower()
                if gated(comp):
                    if blob is None:
                        blob = " ".join(str(v) for v in row.values())
                    if not has_gcc_keyword(blob):
                        drop_companies.add(comp); continue
                if cl in CONN35 and (conn is None or conn < 35):
                    drop_companies.add(comp); continue
                if cl == "amazon" and not amazon_ok(row, exp, prof_hub):
                    drop_companies.add(comp); continue
                if cl == "ntt data group" and not ntt_vizag_ok(row, exp):
                    drop_companies.add(comp)
            if drop_companies:
                ev = {s for s in ev if S2C[s] not in drop_companies}
                nm = {s for s in nm if S2C[s] not in drop_companies}
                ja = {s for s in ja if S2C[s] not in drop_companies}
            if not ev:
                continue
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
            te += 1
            if nm:
                tn += 1
            if ja:
                tj += 1
    return se, sn, sj, ce, cn, cj, te, tn, tj


def main():
    init()
    shards = sorted(glob.glob(os.path.join(C["shards"], "*.csv.gz")))
    print(f"[{TRACK}] slugs {len(S2C):,} | shards {len(shards)} | workers {WORKERS}", flush=True)
    SE = Counter(); SN = Counter(); SJ = Counter(); CE = Counter(); CN = Counter(); CJ = Counter()
    TE = TN = TJ = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for se, sn, sj, ce, cn, cj, te, tn, tj in pool.imap_unordered(worker, shards):
            SE.update(se); SN.update(sn); SJ.update(sj); CE.update(ce); CN.update(cn); CJ.update(cj)
            TE += te; TN += tn; TJ += tj
    comps = set(S2C.values())
    with open(os.path.join(C["out"], "_company_totals_revised.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "ever", "cur_normal", "cur_jani"])
        for comp in sorted(comps, key=lambda c: -CJ.get(c, 0)):
            w.writerow([comp, CE.get(comp, 0), CN.get(comp, 0), CJ.get(comp, 0)])
    by = defaultdict(list)
    for sl, comp in S2C.items():
        by[comp].append(sl)
    with open(os.path.join(C["out"], "_entity_counts_revised.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "slug", "ever", "cur_jani"])
        for comp in sorted(by):
            for sl in sorted(by[comp], key=lambda s: -SE.get(s, 0)):
                w.writerow([comp, sl, SE.get(sl, 0), SJ.get(sl, 0)])
    print(f"\n[{TRACK}] OVERALL (revised, distinct): ever {TE:,} | cur-normal {TN:,} | cur-jani {TJ:,}  ({time.time()-t0:,.0f}s)")
    print("TOP 10 (cur-jani) with entities:")
    for comp in sorted(comps, key=lambda c: -CJ.get(c, 0))[:10]:
        es = [(sl, SJ.get(sl, 0)) for sl in sorted(by[comp], key=lambda s: -SE.get(s, 0)) if SE.get(sl, 0) >= 150]
        print(f"  {comp} | ever {CE.get(comp,0):,} | cur-jani {CJ.get(comp,0):,} | " +
              ", ".join(f"{s}({j:,})" for s, j in es))


if __name__ == "__main__":
    main()
