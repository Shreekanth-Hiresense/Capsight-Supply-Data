# Purpose: ONE consolidated, location-normalized profile file across Track-1 + Track-2 + Part-2, covering
#   EVER-worked (current AND former) at the curated companies. One row per PERSON (dedup by uid across tracks):
#   the 32 ORIGINAL columns (experience[] already holds all jobs/dates/companies/locations) + final_location.
#   Curation = same as counting (final_slugs; EY/Deloitte GCC keyword; MS/Google/Amazon>=35; Amazon hubs/no-sales;
#   NTT=Vizag; Part-2 excludes + LOC_ONLY + interns). NO 11-function filter (file includes former employees).
#   Primary cities per company: tiered cap by CURRENT headcount (>5k=2%,1k-5k=4%,<1k=5%, >=10). final_location
#   per person = best assignment across their companies (direct > current-role-loc(High) > past-role-loc(Low));
#   drop only profiles with no primary evidence anywhere. Two gz scans (phase1 signals -> map; phase2 write).
import ast, csv, glob, gzip, json, os, re, shutil, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

P2DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts"
sys.path.insert(0, P2DIR); sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
from jani_rules import has_gcc_keyword, gated
import gcc_taxonomy_classifier as TC
from disk_guard import check_disk, warn_after_write

csv.field_size_limit(2 ** 31 - 1); sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\AllTracks_profiles_location_tagged.csv.gz"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\locall_parts"
TRACKS = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   col="company", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn", kind="t12"),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn", kind="t12"),
    "part2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv",
                  col="company_target", shards=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards", kind="part2"),
}
VIZAG = ["visakhapatnam", "vishakhapatnam", "vishakapatnam", "vizag", "vskp", "vysac"]
AMZ_HUB = ["hyderabad", "secunderabad", "bengaluru", "bangalore", "mumbai", "navi mumbai", "thane", "chennai",
           "delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad", "coimbatore", "pune"]
AMZ_SALES = re.compile(r"\b(sales|business development|account manager|account executive|territory|relationship manager|field sales|inside sales|channel sales)\b", re.I)
S2C = None; EXCL = None; PART2_IN11 = None


# Recovered (missed) companies pulled by URL -> folded into their tracks (same drill)
REC = {
    "track1": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Recovered_track1_profiles.csv",
    "track2": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Recovered_track2_profiles.csv",
    "part2":  r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Recovered_part2_profiles.csv",
}
NM_XLSX = r"C:\Users\LENOVO\Downloads\Track_Company_Coverage_NotMatched (2).xlsx"
NM_TK = {"Track-1": "track1", "Track-2": "track2", "Track-2 Part-2": "part2"}


def opener(path):
    return (gzip.open(path, "rt", encoding="utf-8", newline="") if path.endswith(".gz")
            else open(path, "rt", encoding="utf-8", newline=""))


def recovered_slugs():
    import openpyxl
    out = {}
    try:
        ws = openpyxl.load_workbook(NM_XLSX, read_only=True, data_only=True)["All_NotMatched"]
        for r in list(ws.iter_rows(values_only=True))[1:]:
            if not r or not (r[0] or (len(r) > 1 and r[1])):
                continue
            raw = str(r[0]).strip() if r[0] else ""
            tk = NM_TK.get(raw, raw) if raw else "track1"
            comp = str(r[1]).strip() if r[1] else ""
            for c in r[2:]:
                if c and "linkedin.com" in str(c):
                    m = re.search(r"/(company|showcase)/([^/?#]+)", str(c))
                    if m:
                        out.setdefault(tk, {})[m.group(2).strip().lower()] = comp
    except Exception as e:
        print("recovered_slugs failed:", e)
    return out


def init():
    global S2C, EXCL, PART2_IN11
    PART2_IN11 = set()                            # Part-2 current-in-11 uids (precomputed; no inline classify)
    p2f = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\part2_in11_uids.txt"
    if os.path.exists(p2f):
        with open(p2f, encoding="utf-8") as fh:
            PART2_IN11 = set(line.strip() for line in fh if line.strip())
    S2C = {}
    for tk, c in TRACKS.items():
        for r in csv.DictReader(open(c["final"], encoding="utf-8")):
            sl = (r.get("slug") or "").strip().lower()
            if sl:
                S2C.setdefault(tk, {})[sl] = (r.get(c["col"]) or "").strip()
    for tk, d in recovered_slugs().items():      # fold recovered companies into their tracks
        S2C.setdefault(tk, {}).update(d)
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


def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v, list) else []
    except Exception:
        return []


def scan(args):
    tk, path = args
    s2c = S2C[tk]; kind = TRACKS[tk]["kind"]
    emit = defaultdict(list)
    with opener(path) as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            exp = parse(row.get("experience"))
            loc_text = ((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower()
            own = P2.canon_city(loc_text)
            cslug = defaultdict(set); ctitle = defaultdict(list); ccur = defaultdict(bool)
            curloc = defaultdict(str); pastloc = defaultdict(set)
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
                        if rloc and not curloc[comp]:
                            curloc[comp] = rloc
                    elif rloc:
                        pastloc[comp].add(rloc)
                    cslug[comp].add(list(hit)[0])
            uid = row.get("uid")
            blob = None; func11 = None   # Part-2 whole-profile 11-function result (computed lazily)
            for comp in cslug:
                cl = comp.strip().lower(); titletext = " ; ".join(ctitle[comp])
                if kind == "t12":
                    if gated(comp):
                        if blob is None:
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
                    # NO 11-function filter on the overall file (overall is never function-filtered).
                emit[comp].append((uid, own or "", 1 if ccur[comp] else 0, curloc.get(comp, ""),
                                   "|".join(sorted(pastloc.get(comp, ())))))
    return emit


CITY2STATE = {
    "bengaluru": "Karnataka", "mysuru": "Karnataka", "mangaluru": "Karnataka",
    "hyderabad": "Telangana", "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu",
    "pune": "Maharashtra", "mumbai mmr": "Maharashtra", "nagpur": "Maharashtra",
    "delhi ncr": "Delhi-NCR (mixed)", "kolkata": "West Bengal", "ahmedabad": "Gujarat",
    "kochi": "Kerala", "trivandrum": "Kerala", "jaipur": "Rajasthan", "indore": "Madhya Pradesh",
    "chandigarh": "Chandigarh Tricity", "bhubaneswar": "Odisha", "visakhapatnam": "Andhra Pradesh",
}
TGT_CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Calibration_targets.csv"
CALIB_OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Calibration_match_ALL_updated.csv"
SECT_MAP_OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\company_sector_map_used.csv"
T1_XLSX = r"C:\Users\LENOVO\Downloads\Track_1_Companies (1).xlsx"
# L2 -> parent L1 (from the user's canonical tables)
L2_L1 = {}
# keyword -> L2 (rough classifier for Track-2/Part-2 companies lacking a sector column)
L2_KW = [
    ("Enterprise Software, SaaS & Digital Platforms", ["software", "saas", "technolog", "systems", "digital", "cloud soft", "erp", "crm", "platform", "infotech", "solutions", "labs", "apps", "it services", "consulting services", "infosys", "tcs", "wipro", "cognizant"]),
    ("Banking, Capital Markets & FinTech", ["bank", "capital", "fintech", "payment", "financial services", "securities", "trading", "jpmorgan", "citi", "hsbc", "barclays", "goldman", "morgan"]),
    ("Industrial Automation, Robotics & Heavy Machinery", ["industr", "automation", "robot", "machinery", "engineering", "manufactur", "siemens", "honeywell", "emerson", "schneider", "bosch", "abb", "hvac", "turbine", "controls"]),
    ("Management Consulting, Strategy & Corporate Advisory", ["consulting", "advisory", "strategy", "mckinsey", "bcg", "bain", "deloitte", "accenture", "kpmg", "pwc", "ey ", "ernst"]),
    ("E-Commerce, Digital Marketplaces & Retail Tech", ["retail", "commerce", "marketplace", "consumer", "fmcg", "walmart", "amazon", "target", "flipkart", "brand"]),
    ("Semiconductor Fabless & Silicon VLSI Design", ["semiconduct", "silicon", "vlsi", "chip", "amd", "nvidia", "intel", "qualcomm", "fabless", "microelectron"]),
    ("Automotive OEMs, Connected Mobility & Auto Components ER&D", ["auto", "vehicle", "mobility", "motor", "toyota", "mercedes", "hyundai", "bmw", "ford", "tier-1", "powertrain"]),
    ("Hospitals, Health Systems & Care Delivery Operations", ["hospital", "health system", "care delivery", "healthcare", "optum", "unitedhealth", "payer"]),
    ("Telecom Networks & Communications Infrastructure", ["telecom", "network", "communications", "wireless", "5g", "cisco", "ericsson", "nokia", "verizon", "vodafone"]),
    ("Biopharmaceuticals, Therapeutics & Drug Discovery", ["pharma", "biopharma", "therapeutic", "drug", "biotech", "pfizer", "novartis", "roche", "merck", "astrazeneca", "vaccine"]),
    ("Oil, Gas, Petrochemicals & Power Utilities", ["oil", "gas", "petro", "energy", "power", "utilit", "shell", "slb", "exxon", "bp ", "refin"]),
    ("Medical Devices, Diagnostic Equipment & Surgical Technologies", ["medical device", "diagnostic", "surgical", "implant", "imaging", "philips", "medtronic", "siemens healthineers", "ge health"]),
    ("Life Sciences Tools, Genomics & Clinical Research (CRO)", ["life sciences", "genomic", "clinical research", "cro", "laboratory", "sequencing", "biostat", "iqvia", "thermo"]),
    ("Logistics, Supply Chain & Freight Operations", ["logistic", "supply chain", "freight", "shipping", "cargo", "dhl", "maersk", "fedex", "courier"]),
    ("Commercial Aviation, Aerospace Systems & Defense", ["aerospace", "aviation", "defense", "defence", "avionic", "boeing", "airbus", "raytheon", "safran", "aero"]),
    ("Travel, Hospitality & Leisure Platforms", ["travel", "hospitality", "hotel", "airline", "leisure", "tourism", "booking", "expedia"]),
    ("Human Capital Management, Talent Solutions & HR Technology", ["human capital", "talent", "hr tech", "staffing", "recruit", "payroll", "workforce", "adp"]),
    ("Insurance, Reinsurance & Actuarial", ["insurance", "reinsurance", "actuar", "underwrit", "allianz", "aig", "aon", "marsh"]),
    ("Data Platforms, AI & Advanced Analytics", ["data platform", "analytics", "artificial intelligence", "machine learning", "databricks", "snowflake", "ai platform"]),
    ("Construction Technology & Real Estate Services", ["construction", "real estate", "facility", "architect", "building information", "bim", "aecom", "cbre", "jll"]),
    ("Digital Media, Gaming, Advertising & Publishing", ["media", "gaming", "game", "advertising", "adtech", "publishing", "entertainment", "studio", "conde"]),
    ("Specialty Chemicals, Advanced Materials & Mining", ["chemical", "materials", "mining", "polymer", "bayer", "basf", "dow", "lithium"]),
    ("Cybersecurity & Identity Management", ["cybersecur", "security", "identity", "endpoint", "siem", "crowdstrike", "palo alto", "okta"]),
    ("Education Technology & Digital Learning", ["education", "edtech", "learning", "e-learning", "lms", "academ", "university", "training"]),
    ("Cloud Infrastructure, DevOps & Developer Tools", ["devops", "developer tools", "ci/cd", "container", "kubernetes", "infrastructure cloud", "api platform"]),
]


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def load_sector_map():
    import openpyxl
    m = {}
    try:
        wb = openpyxl.load_workbook(T1_XLSX, read_only=True, data_only=True)
        for sh in ("Track 1 companies", "Track 1 in top 200"):
            if sh not in wb.sheetnames:
                continue
            ws = wb[sh]; it = ws.iter_rows(values_only=True); hdr = [str(h) for h in next(it)]
            ci = {h: i for i, h in enumerate(hdr)}
            for r in it:
                if r and r[ci["company_name"]]:
                    m[norm(r[ci["company_name"]])] = (r[ci["sector"]] or "", r[ci["l2_industry"]] or "")
    except Exception as e:
        print("  (sector: Track-1 Excel read failed:", str(e)[:60], ")")
    return m


def classify_l2(name):
    n = " " + norm(name) + " "
    for l2, kws in L2_KW:
        if any((" " + norm(k) + " ") in n or norm(k) in norm(name) for k in kws):
            return l2
    return ""


def calibrate(DATA):
    tgt = {"L1": {}, "L2": {}, "CITY": {}, "STATE": {}}
    for r in csv.DictReader(open(TGT_CSV, encoding="utf-8")):
        tgt[r["level"]][r["name"]] = int(r["calibrated_talent"])
    # our-canon city -> target name(s) to sum
    CITY_TGT = {"bengaluru": ["Bengaluru"], "hyderabad": ["Hyderabad"], "chennai": ["Chennai"],
                "pune": ["Pune"], "mumbai mmr": ["Mumbai MMR"],
                "delhi ncr": ["Gurugram", "Noida", "Delhi"], "kolkata": ["Kolkata"],
                "ahmedabad": ["Ahmedabad & GIFT City"], "coimbatore": ["Coimbatore"], "kochi": ["Kochi"],
                "trivandrum": ["Thiruvananthapuram"], "jaipur": ["Jaipur"], "indore": ["Indore"],
                "chandigarh": ["Chandigarh Tricity"], "bhubaneswar": ["Bhubaneswar"], "nagpur": ["Nagpur"],
                "visakhapatnam": ["Visakhapatnam"], "mysuru": ["Mysuru"]}
    sect = load_sector_map()
    sectmap = {}   # company -> (L1,L2)
    for comp in DATA:
        n = norm(comp)
        if n in sect and sect[n][0]:
            sectmap[comp] = sect[n]
        else:
            l2 = classify_l2(comp)
            l1 = next((p for p, kws in [] if False), "")  # fill from L2_L1 below
            sectmap[comp] = ("", l2)
    # L2 -> L1 from targets file (parent column)
    l2l1 = {}
    for r in csv.DictReader(open(TGT_CSV, encoding="utf-8")):
        if r["level"] == "L2":
            l2l1[r["name"]] = r["parent_or_region"]
    for comp, (l1, l2) in list(sectmap.items()):
        if not l1 and l2 in l2l1:
            sectmap[comp] = (l2l1[l2], l2)
    with open(SECT_MAP_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "L1", "L2"])
        for comp in sorted(sectmap):
            w.writerow([comp, sectmap[comp][0], sectmap[comp][1]])
    # current uids + own city.  CURRENT for calibration: Part-2 current must be in the 11 functions
    # (PART2_IN11); Track-1/Track-2 current = Jani. (The FILE itself keeps everyone ever-worked; this
    # restriction only affects the currently-working count.)
    PART2_COMPS = set(S2C.get("part2", {}).values())
    uid_own = {}; cur_uids = set()
    city_c = Counter(); l1_c = Counter(); l2_c = Counter()
    comp_cur = defaultdict(set)
    for comp, recs in DATA.items():
        is_p2 = comp in PART2_COMPS
        for uid, own, iscur, cl, past in recs:
            if iscur:
                if is_p2 and uid not in PART2_IN11:   # Part-2 current kept only if in the 11 functions
                    continue
                cur_uids.add(uid); uid_own.setdefault(uid, own)
                comp_cur[comp].add(uid)
    for uid in cur_uids:
        city_c[uid_own.get(uid, "")] += 1
    state_c = Counter()
    for city, n in city_c.items():
        state_c[CITY2STATE.get(city, "other/unknown")] += n
    for comp, uids in comp_cur.items():
        l1, l2 = sectmap.get(comp, ("", ""))
        if l1:
            l1_c[l1] += len(uids)
        if l2:
            l2_c[l2] += len(uids)
    rows = [["LEVEL", "name", "ours_current", "target", "our/target %"]]
    print(f"\n==== CALIBRATION (currently-working Jani, TODAY's logic) ====  distinct current uids {len(cur_uids):,}")
    for lvl, ours_map, getour in (("L1", tgt["L1"], lambda k: l1_c.get(k, 0)),
                                  ("L2", tgt["L2"], lambda k: l2_c.get(k, 0)),
                                  ("STATE", tgt["STATE"], lambda k: state_c.get(k, 0)),
                                  ("CITY", tgt["CITY"], None)):
        print(f"\n-- {lvl} --")
        for name in sorted(ours_map, key=lambda k: -ours_map[k]):
            t = ours_map[name]
            if lvl == "CITY":
                ours = sum(city_c.get(c, 0) for c in city_c if name in CITY_TGT.get(c, []))
            else:
                ours = getour(name)
            pct = (100 * ours / t) if t else 0
            rows.append([lvl, name, ours, t, round(pct, 1)])
            print(f"   {name[:46]:46s} ours {ours:>8,} | target {t:>8,} | {pct:5.0f}%")
    with open(CALIB_OUT, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
    print(f"\n  -> {CALIB_OUT}\n  -> {SECT_MAP_OUT} (company->sector used; Track-1 from Excel, others keyword-classified=approx)")


def main():
    init()
    t0 = time.time()
    tasks = []
    for tk, c in TRACKS.items():
        for p in sorted(glob.glob(os.path.join(c["shards"], "*.csv.gz"))):
            tasks.append((tk, p))
    for tk, p in REC.items():                     # + recovered (missed) company profiles
        if os.path.exists(p):
            tasks.append((tk, p))
    print(f"PHASE 1 (signals): {len(tasks)} inputs (shards + recovered) | workers 10", flush=True)
    DATA = defaultdict(list)
    with Pool(10, initializer=init) as pool:
        for emit in pool.imap_unordered(scan, tasks):
            for comp, lst in emit.items():
                DATA[comp].extend(lst)
    print(f"  collected {sum(len(v) for v in DATA.values()):,} (profile x company) for {len(DATA):,} companies ({time.time()-t0:,.0f}s)")
    # assign one final_location per uid (best across companies)
    RANK = {"direct": 3, "high": 2, "low": 1}
    best = {}   # uid -> (rank, loc)
    for comp, recs in DATA.items():
        total = len(recs); cur_cnt = sum(r[2] for r in recs)
        pct = 0.02 if cur_cnt > 5000 else (0.04 if cur_cnt >= 1000 else 0.05)
        own_counts = Counter(r[1] for r in recs if r[1])
        primary = {c for c, n in own_counts.items() if n >= 10 and n >= pct * total}
        for uid, own, iscur, cl, past in recs:
            if own and own in primary:
                r = (RANK["direct"], own)
            elif cl and cl in primary:
                r = (RANK["high"], cl)
            else:
                hit = [p for p in past.split("|") if p and p in primary]
                r = (RANK["low"], hit[0]) if hit else None
            if r and (uid not in best or r[0] > best[uid][0]):
                best[uid] = r
    LOC = {uid: loc for uid, (rk, loc) in best.items()}
    # ---- per-track OVERALL (ever) + CURRENTLY-WORKING (Part-2 current = in-11), incl. recovered ----
    comp2track = {}
    for _tk in ("track1", "track2", "part2"):
        for _c in set(S2C.get(_tk, {}).values()):
            comp2track.setdefault(_c, _tk)
    _P2C = set(S2C.get("part2", {}).values())
    t_ever = defaultdict(set); t_cur = defaultdict(set)
    for comp, recs in DATA.items():
        _tk = comp2track.get(comp, "?"); is_p2 = comp in _P2C
        for uid, own, iscur, cl, past in recs:
            t_ever[_tk].add(uid)
            if iscur and not (is_p2 and uid not in PART2_IN11):
                t_cur[_tk].add(uid)
    print("\n==== PER-TRACK (incl. recovered companies) ====")
    ao = set(); ac = set()
    for _tk in ("track1", "track2", "part2"):
        print(f"  {_tk:8s} overall(ever) {len(t_ever[_tk]):>10,} | currently-working {len(t_cur[_tk]):>10,}")
        ao |= t_ever[_tk]; ac |= t_cur[_tk]
    print(f"  {'TOTAL':8s} overall(distinct) {len(ao):>10,} | current(distinct) {len(ac):>10,}")
    calibrate(DATA)   # city/state/L1/L2 calibration vs targets (from the same scan's DATA)
    print(f"  tagged profiles (distinct uid): {len(LOC):,}; writing consolidated file...", flush=True)
    check_disk(len(LOC) * 2500 / 1e9, label="AllTracks consolidated")
    # PHASE 2: write 32 cols + final_location, dedup by uid across tracks
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    seen = set(); written = 0; cols0 = None
    with gzip.open(OUT, "wt", encoding="utf-8", newline="") as fo:   # gzip: ~8-10GB not ~50GB
        w = None
        for tk, p in tasks:                       # same inputs as phase 1 (shards + recovered)
            with opener(p) as f:
                rd = csv.DictReader(f); cols = rd.fieldnames
                if w is None:
                    cols0 = cols; w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols + ["final_location"])
                for row in rd:
                    uid = row.get("uid")
                    if uid in LOC and uid not in seen:
                        seen.add(uid)
                        w.writerow([row.get(cc, "") for cc in cols0] + [LOC[uid]]); written += 1
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n==== DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  consolidated profiles written (distinct uid): {written:,}")
    print(f"  columns: {len(cols0)+1} (32 original + final_location)")
    print(f"  -> {OUT}")
    warn_after_write(OUT)


if __name__ == "__main__":
    main()
