# Purpose: TRACK-2 PART-2 negation + city engine (v1, iterate per step 6). One pass over the pulled Part-2
#   shards. For each company: take its India employees with connections>=20 (exclude interns/trainees),
#   REMOVE people whose CURRENT role / headline matches that company's negate-L3 categories (col B) and
#   remove domestic Sales Operations -- BUT never remove (a) anyone on a GCC-named entity page, or (b) with
#   an R&D/software/research/analyst/engineering-office title, and KEEP Revenue Operations (bids/deal desk/
#   sales enablement/incentive comp). Count kept people by city (Delhi NCR / Mumbai MMR grouped); if a
#   company's India total < CUTOFF (env, default 70) tag all to its largest city. Output Excel:
#   Company | India total | Final location | People removed  (+ a diagnostics CSV of sample removals).
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
import openpyxl

csv.field_size_limit(2 ** 31 - 1)
PART2_XLSX = r"C:\Users\LENOVO\Downloads\Track2_Part2_Domestic_L3_Negation_v2 (1).xlsx"
FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv"
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards"
OUT_XLSX = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_India_GCC_by_city.xlsx"
WORKERS = 12
CUTOFF = int(os.environ.get("CUTOFF", "70"))

# ---- 24 negate-L3 category -> title/role patterns (v1; refine on review) ----
CAT = {
 "Field & Territory Sales (India market)": r"field sales|territory sales|territory manager|area sales|sales officer|sales executive|field officer|regional sales|zonal sales|\basm\b|territory business",
 "Sales Operations (GCC L3, domestic only)": r"sales operation|sales ops|sales coordinator|sales support|order management|sales admin",
 "Warehouse / Depot & Last-Mile Logistics Operations": r"warehouse|depot|last.?mile|logistics operation|dispatch|material handling|godown|delivery (boy|associate|executive)",
 "Plant Quality Control (in-plant QC / QA)": r"quality control|quality inspector|incoming quality|in.?process quality|\biqc\b|line quality|shop.?floor quality",
 "Plant Production & Shop-Floor Operations": r"\bproduction\b|shop.?floor|machine operator|line operator|plant operator|production supervisor|manufacturing operator",
 "Plant Maintenance & Utilities": r"plant maintenance|maintenance engineer|maintenance technician|utilities|preventive maintenance|mechanical maintenance|electrical maintenance",
 "Field Service & After-Sales (installation and servicing in India)": r"field service|service engineer|after.?sales|installation|commissioning|service technician|field application",
 "Channel / Distributor & Dealer Development": r"channel sales|distributor|\bdealer\b|channel development|channel partner|primary sales|secondary sales|trade sales",
 "Government / PSU Liaison & Tender Sales": r"\btender|government sales|\bpsu\b|govt|public sector sales|liaison",
 "On-ground Trade Marketing & Merchandising (India)": r"trade marketing|merchandis|in.?store|\bpromoter\b|brand promoter",
 "Project Site Execution & Construction (Indian projects)": r"site engineer|project site|construction|site execution|site supervisor|erection|civil engineer",
 "Modern Trade / Institutional / Key-Account Sales India": r"modern trade|key account|institutional sales|national account",
 "Indian Regulatory Licensing & Statutory Liaison": r"regulatory affairs|statutory|licensing|liaison officer|government liaison",
 "Medical Device Clinical & Application Specialists (field)": r"clinical application|application specialist|clinical specialist|product specialist",
 "Pharma / Healthcare Field Force": r"medical representative|\bmr\b|pharma field|medical rep|detailing|territory business manager",
 "Retail Store Operations": r"store manager|retail store|store operation|floor manager|\bcashier\b|store associate|\boutlet\b",
 "Hotel & Hospitality Operations": r"\bhotel\b|hospitality|front office|housekeeping|\bchef\b|f&b|guest service",
 "Branch Banking & Retail Financial Sales (India)": r"branch banking|branch manager|retail banking|personal banker|branch operation|\bteller\b|relationship manager",
 "Dealership / Showroom Sales & Workshop (auto)": r"showroom|dealership|service advisor|vehicle sales|auto sales",
 "Airline & Airport Station Operations (India)": r"airport|ground staff|cabin crew|station operation|\bramp\b|airline operation",
 "Inspection / Testing / Certification Field Services": r"\binspection\b|\bsurveyor\b|\bndt\b|field inspection|testing.{0,10}certification",
 "On-site Facility Services Delivery (FM / catering)": r"facility management|facilities|catering|\bfm services|soft services",
 "Agronomy & Farmer Field Services": r"agronom|\bfarmer|agri.?field|\bkrishi",
 "Security Guarding Operations": r"security guard|guarding|security officer",
}
CAT_RE = {k: re.compile(v, re.I) for k, v in CAT.items()}

PROTECT_TITLE = re.compile(
    r"\b(software|developer|\bsde\b|r&d|research|data scien|data analyst|analytics|architect|devops|\bsre\b|"
    r"machine learning|\bml\b|\bai\b|cloud|platform|full.?stack|backend|front.?end|sdet|product manager|"
    r"program manager|designer|scientist|\bqa engineer|test engineer|firmware|embedded|validation engineer|"
    r"analyst|finance|accounting|\btax\b|\behs\b|brand|revenue operation|deal desk|sales enablement|"
    r"incentive comp|bid manager|pricing)\b", re.I)
GCC_ENTITY = re.compile(r"technolog|global|capability|\bgbs\b|r&d|digital|shared.?service|\bgic\b|\bgcc\b|innovation|engineering center|engineering centre|development cent", re.I)
INTERN = re.compile(r"\bintern\b|internship|\btrainee\b|apprentice|\bstudent\b", re.I)

# per-company overrides (lowercased company label)
EXCLUDE_P2 = {"ibm", "hp", "ntt", "bosch", "people tech"}        # drop entirely (handled elsewhere / not wanted)
# raw location-token whitelist per company (matched against profile address+region, lowercased)
LOC_ONLY_P2 = {"teleperformance": ["hyderabad", "secunderabad", "gurgaon", "gurugram"],
               "siemens": ["bengaluru", "bangalore", "chennai", "pune", "delhi", "new delhi",
                           "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad"],
               "philips": ["bengaluru", "bangalore", "chennai", "delhi", "new delhi",
                           "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad"]}

import unicodedata as _ud
_LEGAL = {"private", "limited", "pvt", "ltd", "llp", "inc", "incorporated", "corporation", "corp",
          "llc", "gmbh", "plc", "sa", "ag", "nv", "bv", "co", "company", "holdings"}


def cnorm(s):
    s = _ud.normalize("NFKD", str(s) or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip(); t = s.split()
    while t and t[-1] in _LEGAL:
        t.pop()
    return " ".join(t)


T1_FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
T2_FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv"
S2C = None; NEG = None; EXCLUDE_NORMS = None


def load_targets():
    import unicodedata
    def norm(s):
        s = unicodedata.normalize("NFKD", str(s) or "").encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", " ", s).strip()
    wb = openpyxl.load_workbook(PART2_XLSX, read_only=True, data_only=True)
    ws = wb["Company - L3s to negate"]; rows = ws.iter_rows(values_only=True); next(rows)
    neg = {}
    for r in rows:
        if not r[0]:
            continue
        cats = []
        if r[1] and not str(r[1]).strip().lower().startswith("none"):
            for part in str(r[1]).split(";"):
                p = part.strip()
                if p in CAT_RE:
                    cats.append(p)
        neg[str(r[0]).strip()] = cats
    return neg


def init():
    global S2C, NEG, EXCLUDE_NORMS
    S2C = {}
    for r in csv.DictReader(open(FINAL, encoding="utf-8")):
        sl = (r.get("slug") or "").strip().lower()
        if sl:
            S2C[sl] = r.get("company_label") or r.get("company_target") or ""
    NEG = load_targets()
    # exclude: manual (ibm/hp/ntt/bosch) + any company already in Track-1 or Track-2
    EXCLUDE_NORMS = {cnorm(x) for x in EXCLUDE_P2}
    for f, col in ((T1_FINAL, "company"), (T2_FINAL, "company_target")):
        try:
            for r in csv.DictReader(open(f, encoding="utf-8")):
                v = r.get(col)
                if v:
                    EXCLUDE_NORMS.add(cnorm(v))
        except FileNotFoundError:
            pass


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

# city canonicalisation
CITY = [
 ("delhi ncr", ["new delhi", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad", "greater noida"]),
 ("mumbai mmr", ["navi mumbai", "mumbai", "thane", "kalyan", "vasai"]),
 ("bengaluru", ["bengaluru", "bangalore"]),
 ("hyderabad", ["hyderabad", "secunderabad"]),
 ("chennai", ["chennai"]), ("pune", ["pune"]), ("kolkata", ["kolkata"]),
 ("ahmedabad", ["ahmedabad"]), ("coimbatore", ["coimbatore"]), ("visakhapatnam", ["visakhapatnam", "vizag"]),
 ("jaipur", ["jaipur"]), ("chandigarh", ["chandigarh", "mohali"]), ("kochi", ["kochi", "cochin"]),
 ("indore", ["indore"]), ("nagpur", ["nagpur"]), ("trivandrum", ["thiruvananthapuram", "trivandrum"]),
 ("bhubaneswar", ["bhubaneswar"]), ("mysuru", ["mysuru", "mysore"]),
]


def canon_city(addr):
    t = (addr or "").lower()
    for canon, al in CITY:
        for a in al:
            if a in t:
                return canon
    return None


def current_title_blob(exp, slugs_for_comp):
    """headline-ish text of the person's CURRENT role(s) at this company + overall current title"""
    titles = []
    for e in exp:
        if not isinstance(e, dict):
            continue
        dur = e.get("duration") or {}
        cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
        if cur:
            titles.append(e.get("title") or "")
    return " ; ".join(titles)


def worker(path):
    # per company: kept city counter, removed count, intern/abroad/lowconn drop (info)
    kept = defaultdict(Counter)      # company -> city -> n (ever)
    kept_cur = defaultdict(Counter)  # company -> city -> n (currently working, Jani)
    removed = Counter()              # company -> n removed by negation
    samples = []                     # (company, title, matched_cat)  up to a few per shard
    te = tj = 0                      # overall distinct: kept(ever) / kept-and-currently-working
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
            loc_text = ((row.get("miniprofile_location_address") or "") + " " +
                        (row.get("miniprofile_location_region") or "")).lower()
            city = canon_city(loc_text)
            # per company (by slug): slugs matched + the person's role TITLES at that company
            comp_slugs = defaultdict(set); comp_titles = defaultdict(list); comp_cur = defaultdict(bool)
            for e in exp:
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & S2C.keys()
                if not hit:
                    continue
                title = e.get("title") or ""
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                for comp in {S2C[s] for s in hit}:
                    comp_titles[comp].append(title)
                    if is_cur:
                        comp_cur[comp] = True
                for s in hit:
                    comp_slugs[S2C[s]].add(s)
            prof_kept = prof_cur = False
            for comp, sls in comp_slugs.items():
                cl = comp.strip().lower()
                if cl in EXCLUDE_P2 or cnorm(comp) in EXCLUDE_NORMS:
                    continue   # dropped entirely (manual, or already in Track-1/2)
                allowed = LOC_ONLY_P2.get(cl)
                if allowed is not None and not any(tok in loc_text for tok in allowed):
                    continue   # company restricted to specific location tokens
                titletext = " ; ".join(comp_titles.get(comp, []))   # v2: match on job TITLE(s) at this company only
                if INTERN.search(titletext):
                    continue   # interns/trainees -> out of scope
                negcats = NEG.get(comp, [])
                on_gcc_entity = any(GCC_ENTITY.search(s) for s in sls)
                protected = on_gcc_entity or bool(PROTECT_TITLE.search(titletext))
                drop = False
                if negcats and not protected:
                    for c in negcats:
                        if CAT_RE[c].search(titletext):
                            drop = True
                            if len(samples) < 40:
                                samples.append((comp, titletext[:60], c))
                            break
                if drop:
                    removed[comp] += 1
                else:
                    kept[comp][city or "unknown"] += 1
                    prof_kept = True
                    if comp_cur.get(comp):
                        kept_cur[comp][city or "unknown"] += 1
                        prof_cur = True
            te += 1 if prof_kept else 0
            tj += 1 if prof_cur else 0
    return kept, removed, samples, kept_cur, te, tj


def main():
    init()
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"companies(final) {len(set(S2C.values())):,} | shards {len(shards)} | CUTOFF {CUTOFF} | workers {WORKERS}", flush=True)
    KEPT = defaultdict(Counter); KEPT_CUR = defaultdict(Counter); REMOVED = Counter(); SAMP = []
    TE = TJ = 0
    t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for kept, removed, samples, kept_cur, te, tj in pool.imap_unordered(worker, shards):
            for comp, cc in kept.items():
                KEPT[comp].update(cc)
            for comp, cc in kept_cur.items():
                KEPT_CUR[comp].update(cc)
            REMOVED.update(removed); TE += te; TJ += tj
            if len(SAMP) < 60:
                SAMP.extend(samples[:5])
    # build output rows
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Part2 India GCC by city"
    ws.append(["Company Name", "India total", "Currently working", "Currently-working location (city: count)", "People removed"])
    for comp in sorted(KEPT, key=lambda c: -sum(KEPT[c].values())):
        cc = KEPT[comp]
        india = sum(cc.values())
        if india == 0:
            continue
        curcc = KEPT_CUR.get(comp, Counter())
        cur = sum(curcc.values())
        # small-N rule on the currently-working count: if under CUTOFF, tag all to the largest city
        named = {k: v for k, v in curcc.items() if k != "unknown"}
        if 0 < cur < CUTOFF and named:
            top = max(named, key=named.get)
            locstr = f"{top}: {cur}"
        else:
            locstr = ", ".join(f"{k}: {v}" for k, v in sorted(curcc.items(), key=lambda x: -x[1]))
        ws.append([comp, india, cur, locstr, REMOVED.get(comp, 0)])
    wb.save(OUT_XLSX)
    # diagnostics
    with open(os.path.join(os.path.dirname(FINAL), "_negation_samples.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["company", "title/headline", "matched_negate_category"])
        for s in SAMP:
            w.writerow(s)
    tot_india = sum(sum(c.values()) for c in KEPT.values())
    tot_removed = sum(REMOVED.values())
    print(f"\n==== PART-2 NEGATION DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  companies with India>0 : {sum(1 for c in KEPT if sum(KEPT[c].values())>0):,}")
    print(f"  India total (kept, sum over companies) : {tot_india:,}")
    print(f"  removed by negation (sum)              : {tot_removed:,}")
    print(f"  OVERALL distinct profiles (India)      : {TE:,}")
    print(f"  OVERALL distinct CURRENTLY working     : {TJ:,}")
    print(f"  -> {OUT_XLSX}  (+ _negation_samples.csv)")


if __name__ == "__main__":
    main()
