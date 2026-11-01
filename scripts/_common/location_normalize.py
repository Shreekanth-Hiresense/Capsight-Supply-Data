# Purpose: Company-wise LOCATION NORMALISATION across all 3 tracks' currently-working (Jani) profiles.
#   Steps (user spec 2026-10-29): group each company's current profiles by city; PRIMARY locations = cities
#   with >=5% of that company's profiles AND >=10 profiles; DIRECT-tag profiles already in a primary location;
#   REASSIGN the rest to the most relevant primary location using evidence (current-role location High, profile
#   region Medium, past-role location Low); EXCLUDE profiles with no evidence for any primary; reconcile
#   direct+reassigned+excluded = total per company. Output table Company|Location|Original|Reassigned|Final|
#   Excluded|Confidence (Excel + CSV). Per-track current logic + gates reused from combined_current_by_city:
#   T1/T2 = Jani + EY/Deloitte keyword + MS/Google/Amazon>=35 + Amazon hubs/no-sales + NTT=Vizag; Part-2 =
#   Jani + excludes + LOC_ONLY + interns + the Capsight 11-function keep (NO col-B negation). Read-only.
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

P2DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts"
sys.path.insert(0, P2DIR)
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
from jani_rules import has_gcc_keyword, gated
import gcc_taxonomy_classifier as TC

csv.field_size_limit(2 ** 31 - 1)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT_XLSX = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Location_Normalized.xlsx"
OUT_CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Location_Normalized.csv"
CACHE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\_locnorm_cache.csv.gz"


def primary_pct(total):
    # tiered cap by company currently-working headcount (user 2026-10-29)
    return 0.02 if total > 5000 else (0.04 if total >= 1000 else 0.05)

TRACKS = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   col="company", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn", kind="t12"),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn", kind="t12"),
    "part2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv",
                  col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards", kind="part2"),
}
VIZAG = ["visakhapatnam", "vishakhapatnam", "vishakapatnam", "vizag", "vskp", "vysac"]
AMZ_HUB = ["hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai", "navi mumbai", "thane",
           "chennai", "delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad",
           "coimbatore", "pune"]
AMZ_SALES = re.compile(r"\b(sales|business development|account manager|account executive|territory|"
                       r"relationship manager|field sales|inside sales|channel sales)\b", re.I)
S2C = None; EXCL = None; COMP = None


def init():
    global S2C, EXCL, COMP
    S2C = {}
    for tk, c in TRACKS.items():
        for r in csv.DictReader(open(c["final"], encoding="utf-8")):
            sl = (r.get("slug") or "").strip().lower()
            if sl:
                S2C.setdefault(tk, {})[sl] = (r.get(c["col"]) or "").strip()
    EXCL = {P2.cnorm(x) for x in P2.EXCLUDE_P2}
    for f, col in ((TRACKS["track1"]["final"], "company"), (TRACKS["track2"]["final"], "company_target")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get(col):
                EXCL.add(P2.cnorm(r[col]))
    COMP = TC.load()


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
        try:
            return json.loads(x or "[]")
        except Exception:
            return []


def worker(args):
    tk, path = args
    s2c = S2C[tk]; kind = TRACKS[tk]["kind"]
    # emit per (company): (own_city, cur_role_city, frozenset(past_cities))
    emit = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            exp = parse(row.get("experience"))
            if not isinstance(exp, list):
                exp = []
            loc_text = ((row.get("miniprofile_location_address") or "") + " "
                        + (row.get("miniprofile_location_region") or "")).lower()
            own_city = P2.canon_city(loc_text)
            cslug = defaultdict(set); ctitle = defaultdict(list); ccur = defaultdict(bool)
            cur_roleloc = defaultdict(str); past_loc = defaultdict(set)
            cur_title = ""; past_titles = []; descs = []
            for e in exp:
                if not isinstance(e, dict):
                    continue
                t = e.get("title") or ""
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if is_cur and not cur_title:
                    cur_title = t
                else:
                    past_titles.append(t)
                if e.get("description"):
                    descs.append(str(e.get("description")))
                hit = role_slugs(e.get("company") or {}) & s2c.keys()
                if not hit:
                    continue
                rloc = P2.canon_city((e.get("location") or "").lower())
                for comp in {s2c[s] for s in hit}:
                    ctitle[comp].append(t)
                    if is_cur:
                        ccur[comp] = True
                        if rloc and not cur_roleloc[comp]:
                            cur_roleloc[comp] = rloc
                    elif rloc:
                        past_loc[comp].add(rloc)
                for s in hit:
                    cslug[s2c[s]].add(s)
            # which companies qualify as CURRENT (gates), and classify once for part2
            classified = None
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
                    if cl == "amazon" and (not any(h in loc_text for h in AMZ_HUB) or AMZ_SALES.search(titletext)):
                        continue
                    if cl == "ntt data group" and not any(v in loc_text for v in VIZAG):
                        continue
                else:
                    if cl in P2.EXCLUDE_P2 or P2.cnorm(comp) in EXCL:
                        continue
                    allowed = P2.LOC_ONLY_P2.get(cl)
                    if allowed is not None and not any(tok in loc_text for tok in allowed):
                        continue
                    if P2.INTERN.search(titletext):
                        continue
                    if classified is None:
                        skills = parse(row.get("skill"))
                        sk = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
                        res = TC.classify(row.get("miniprofile_headline"), cur_title, sk,
                                          " ; ".join(past_titles), row.get("miniprofile_summary"),
                                          " ".join(descs), COMP)
                        classified = TC.map_to_user11(res["L1"], res["L2"], res["L3_Role"])
                    if not classified:          # Part-2 keeps only the 11 functions
                        continue
                emit[comp].append((tk, row.get("uid"), own_city or "", cur_roleloc.get(comp, ""),
                                   frozenset(past_loc.get(comp, ()))))
    return emit


def main():
    init()
    t0 = time.time()
    DATA = defaultdict(list)
    if os.path.exists(CACHE) and os.environ.get("REBUILD") != "1":
        with gzip.open(CACHE, "rt", encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                tk, comp, uid, own, cur, past = row
                DATA[comp].append((tk, uid, own, cur, frozenset(p for p in past.split("|") if p)))
        print(f"loaded {sum(len(v) for v in DATA.values()):,} cached records for {len(DATA):,} companies "
              f"(set REBUILD=1 to re-scan)", flush=True)
    else:
        tasks = []
        for tk, c in TRACKS.items():
            for p in sorted(glob.glob(os.path.join(c["shards"], "*.csv.gz"))):
                tasks.append((tk, p))
        print(f"shards {len(tasks)} across 3 tracks | workers 10 (scanning; will cache)", flush=True)
        with Pool(10, initializer=init) as pool:
            for emit in pool.imap_unordered(worker, tasks):
                for comp, lst in emit.items():
                    DATA[comp].extend(lst)
        with gzip.open(CACHE, "wt", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for comp, recs in DATA.items():
                for tk, uid, own, cur, past in recs:
                    w.writerow([tk, comp, uid, own, cur, "|".join(sorted(past))])
        print(f"scanned+cached {sum(len(v) for v in DATA.values()):,} records for {len(DATA):,} companies "
              f"({time.time()-t0:,.0f}s)", flush=True)
    print("normalising (tiered cap: >5k=2%, 1k-5k=4%, <1k=5%)...", flush=True)
    out_rows = []
    PROF = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Location_Normalized_profiles.csv"
    pf = open(PROF, "w", newline="", encoding="utf-8")
    pw = csv.writer(pf, quoting=csv.QUOTE_ALL)
    pw.writerow(["uid", "track", "company", "final_location", "confidence", "status"])
    for comp in sorted(DATA, key=lambda c: -len(DATA[c])):
        recs = DATA[comp]; total = len(recs)
        own_counts = Counter(r[2] for r in recs if r[2])
        pct = primary_pct(total)
        primary = {city for city, n in own_counts.items()
                   if n >= 10 and n >= pct * total}
        direct = Counter(); reassigned = Counter(); conf = defaultdict(Counter); excluded = 0
        for tk, uid, own, curloc, past in recs:
            if own and own in primary:
                direct[own] += 1; conf[own]["Direct"] += 1
                pw.writerow([uid, tk, comp, own, "High", "tagged"])
            elif curloc and curloc in primary:
                reassigned[curloc] += 1; conf[curloc]["High"] += 1
                pw.writerow([uid, tk, comp, curloc, "High", "reassigned"])
            else:
                hit = [p for p in past if p in primary]
                if hit:
                    reassigned[hit[0]] += 1; conf[hit[0]]["Low"] += 1
                    pw.writerow([uid, tk, comp, hit[0], "Low", "reassigned"])
                else:
                    excluded += 1
                    pw.writerow([uid, tk, comp, "", "", "excluded"])
        for loc in sorted(primary, key=lambda l: -(direct[l] + reassigned[l])):
            fin = direct[loc] + reassigned[loc]
            cc = conf[loc]
            label = "High" if (cc["Direct"] + cc["High"]) >= 0.8 * fin else ("Mixed" if fin else "-")
            out_rows.append([comp, loc, direct[loc], reassigned[loc], fin, excluded, label])
    pf.close()
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["Company", "Location", "Original Profiles", "Reassigned Profiles",
                    "Final Profiles", "Excluded Profiles", "Confidence"])
        w.writerows(out_rows)
    try:
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "LocationNormalized"
        ws.append(["Company", "Location", "Original Profiles", "Reassigned Profiles",
                   "Final Profiles", "Excluded Profiles", "Confidence"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in out_rows:
            ws.append(r)
        wb.save(OUT_XLSX)
    except Exception as e:
        print("xlsx skipped:", e)
    tot_final = sum(r[4] for r in out_rows)
    print(f"\n==== DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  companies {len(DATA):,} | (company,location) rows {len(out_rows):,} | final tagged {tot_final:,}")
    print(f"  -> count table : {OUT_CSV}\n  -> count table : {OUT_XLSX}")
    print(f"  -> PER-PROFILE normalized (uid,track,company,final_location,confidence,status): {PROF}")
    print("\n  sample (top 25 rows):")
    print(f"  {'company':24s} {'location':16s} {'orig':>7} {'reass':>7} {'final':>7} {'excl':>8} conf")
    for r in out_rows[:25]:
        print(f"  {r[0][:24]:24s} {r[1][:16]:16s} {r[2]:>7,} {r[3]:>7,} {r[4]:>7,} {r[5]:>8,} {r[6]}")


if __name__ == "__main__":
    main()
