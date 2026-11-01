# Purpose: Combined CURRENTLY-WORKING (Jani) distinct-by-city/state across Track-1 + Track-2 + Track-2 Part-2,
#   de-duplicated by uid (a person currently-working in >1 track counts once), with all per-track gates applied
#   (EY/Deloitte GCC-keyword, MS/Google/Amazon >=35 conn, Amazon hub+no-sales, NTT=Vizag; Part-2 negation +
#   excludes + location limits + interns). Then compares our city/state totals to the calibrated TARGETs and
#   writes a matching/not-matching table. Reuses part2_negation's regex/config + jani_rules.
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
P2DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts"
sys.path.insert(0, P2DIR)
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
from jani_rules import has_gcc_keyword, gated

JANI = "Jani"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Calibration_match_city_state.csv"

TRACKS = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   col="company", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn", kind="t12"),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn", kind="t12"),
    "part2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv",
                  col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards", kind="part2"),
}

CITY2STATE = {
 "bengaluru": "Karnataka", "mysuru": "Karnataka", "mangaluru": "Karnataka",
 "hyderabad": "Telangana", "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu",
 "pune": "Maharashtra", "mumbai mmr": "Maharashtra", "nagpur": "Maharashtra",
 "delhi ncr": "Delhi-NCR (mixed)", "kolkata": "West Bengal", "ahmedabad": "Gujarat",
 "kochi": "Kerala", "trivandrum": "Kerala", "jaipur": "Rajasthan", "indore": "Madhya Pradesh",
 "chandigarh": "Chandigarh Tricity", "bhubaneswar": "Odisha", "visakhapatnam": "Andhra Pradesh",
}

# TARGET city (our-canon grouped): Delhi-NCR = Delhi+Gurugram+Noida; Mumbai MMR as given
TARGET_CITY = {
 "bengaluru": 933550, "hyderabad": 434516, "chennai": 389236, "pune": 311227, "mumbai mmr": 292107,
 "delhi ncr": 209001 + 81825 + 40028, "kolkata": 41192, "ahmedabad": 32808, "coimbatore": 23240,
 "kochi": 9935, "trivandrum": 7581, "jaipur": 6525, "indore": 5970, "chandigarh": 4133,
 "bhubaneswar": 3243, "nagpur": 2978, "visakhapatnam": 2846, "mysuru": 902,
}
TARGET_STATE = {
 "Karnataka": 936807, "Maharashtra": 607034, "Telangana": 434516, "Tamil Nadu": 413115,
 "West Bengal": 41192, "Gujarat": 43095, "Kerala": 17516, "Rajasthan": 6525, "Madhya Pradesh": 5970,
 "Odisha": 3243, "Andhra Pradesh": 3380,
}

VIZAG = ["visakhapatnam", "vishakhapatnam", "vishakapatnam", "vizag", "vskp", "vysac"]
AMZ_HUB = ["hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai", "navi mumbai", "thane",
           "chennai", "delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad",
           "coimbatore", "pune"]
AMZ_SALES = re.compile(r"\b(sales|business development|account manager|account executive|territory|"
                       r"relationship manager|field sales|inside sales|channel sales)\b", re.I)
S2C = None; NEG = None; EXCL = None


def init():
    global S2C, NEG, EXCL
    S2C = {}
    for tk, c in TRACKS.items():
        for r in csv.DictReader(open(c["final"], encoding="utf-8")):
            sl = (r.get("slug") or "").strip().lower()
            if sl:
                S2C.setdefault(tk, {})[sl] = (r.get(c["col"]) or "").strip()
    NEG = P2.load_targets()
    EXCL = {P2.cnorm(x) for x in P2.EXCLUDE_P2}
    for f, col in ((TRACKS["track1"]["final"], "company"), (TRACKS["track2"]["final"], "company_target")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get(col):
                EXCL.add(P2.cnorm(r[col]))


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


def worker(args):
    tk, path = args
    s2c = S2C[tk]; kind = TRACKS[tk]["kind"]
    found = {}   # uid -> canon_city
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            if not isinstance(exp, list):
                exp = []
            uid = row.get("uid")
            loc_text = ((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower()
            city = P2.canon_city(loc_text)
            # per-company: slugs, titles, current flag
            cslug = defaultdict(set); ctitle = defaultdict(list); ccur = defaultdict(bool)
            for e in exp:
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & s2c.keys()
                if not hit:
                    continue
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                t = e.get("title") or ""
                for comp in {s2c[s] for s in hit}:
                    ctitle[comp].append(t)
                    if is_cur:
                        ccur[comp] = True
                for s in hit:
                    cslug[s2c[s]].add(s)
            current_somewhere = False
            for comp, sls in cslug.items():
                if not ccur.get(comp):
                    continue
                cl = comp.strip().lower()
                titletext = " ; ".join(ctitle[comp])
                if kind == "t12":
                    if gated(comp):
                        blob = " ".join(str(v) for v in row.values())
                        if not has_gcc_keyword(blob):
                            continue
                    if cl in ("microsoft", "google", "amazon") and (conn is None or conn < 35):
                        continue
                    if cl == "amazon":
                        if not any(h in loc_text for h in AMZ_HUB) or AMZ_SALES.search(titletext):
                            continue
                    if cl == "ntt data group" and not any(v in loc_text for v in VIZAG):
                        continue
                else:  # part2
                    if cl in P2.EXCLUDE_P2 or P2.cnorm(comp) in EXCL:
                        continue
                    allowed = P2.LOC_ONLY_P2.get(cl)
                    if allowed is not None and not any(tok in loc_text for tok in allowed):
                        continue
                    if P2.INTERN.search(titletext):
                        continue
                    negcats = NEG.get(comp, [])
                    on_gcc = any(P2.GCC_ENTITY.search(s) for s in sls)
                    protected = on_gcc or bool(P2.PROTECT_TITLE.search(titletext))
                    if negcats and not protected and any(P2.CAT_RE[c].search(titletext) for c in negcats):
                        continue
                current_somewhere = True
                break
            if current_somewhere:
                found[uid] = city or "unknown"
    return found


def main():
    init()
    tasks = []
    for tk, c in TRACKS.items():
        for p in sorted(glob.glob(os.path.join(c["shards"], "*.csv.gz"))):
            tasks.append((tk, p))
    print(f"shards total {len(tasks)} across 3 tracks", flush=True)
    uid_city = {}
    t0 = time.time()
    with Pool(10, initializer=init) as pool:
        for found in pool.imap_unordered(worker, tasks):
            uid_city.update(found)   # dedup by uid; city same per profile
    citycnt = Counter(uid_city.values())
    statecnt = Counter()
    for city, n in citycnt.items():
        statecnt[CITY2STATE.get(city, "other/unknown")] += n
    total = sum(citycnt.values())
    print(f"\n==== COMBINED currently-working (distinct across 3 tracks): {total:,} ({time.time()-t0:,.0f}s) ====")
    rows = [["LEVEL", "name", "our_current", "target", "diff", "our/target %"]]
    print("\nCITY  (our vs target; target Delhi-NCR = Delhi+Gurugram+Noida):")
    for city in sorted(TARGET_CITY, key=lambda c: -TARGET_CITY[c]):
        ours = citycnt.get(city, 0); tgt = TARGET_CITY[city]
        print(f"  {city:14s} ours {ours:>8,} | target {tgt:>8,} | {100*ours/tgt:5.0f}%")
        rows.append(["city", city, ours, tgt, ours - tgt, round(100 * ours / tgt, 1)])
    print(f"  {'(unknown city)':14s} ours {citycnt.get('unknown',0):>8,}")
    print("\nSTATE:")
    for st in sorted(TARGET_STATE, key=lambda s: -TARGET_STATE[s]):
        ours = statecnt.get(st, 0); tgt = TARGET_STATE[st]
        print(f"  {st:22s} ours {ours:>8,} | target {tgt:>8,} | {100*ours/tgt:5.0f}%")
        rows.append(["state", st, ours, tgt, ours - tgt, round(100 * ours / tgt, 1)])
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
