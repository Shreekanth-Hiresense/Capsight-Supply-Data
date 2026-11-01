# Purpose: STEP 3 - company-to-centre mapping. For every unique company in our master list, compute city-wise
#   DISTINCT-profile counts from OUR pulled data (Delhi-NCR grouped via canon_city), attach the validated
#   industry (from Company_Master_List_industry.csv), and cross-reference the GCC master's per-city headcounts
#   to mark CONFIRMED centres (company has that city in the GCC master) vs PROFILE-ONLY (city present only in
#   our profile data). One row per company: industry_L1/L2, total profiles (ever + current), the centres with
#   per-city counts, confirmed vs profile-only, and an evidence flag. Also records companies seen in data but
#   not yet in the master (to add). Scans track shards + recovered CSVs. Delhi-NCR stays grouped.
import ast, csv, glob, gzip, json, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts")
import part2_negation as P2
import openpyxl

csv.field_size_limit(2 ** 31 - 1); sys.stdout.reconfigure(encoding="utf-8", errors="replace")
JC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
MASTER_CSV = os.path.join(JC, "Company_Master_List_industry.csv")
GCC_XLSX = r"C:\Users\LENOVO\Downloads\gcc master list (2).xlsx"
OUT = os.path.join(JC, "Company_Centre_Mapping.csv")
INPUTS = [
    ("track1", os.path.join(JC, r"Track1_BySlug_profiles\shards_min20conn")),
    ("track2", os.path.join(JC, r"Track2_BySlug_profiles\shards_min20conn")),
    ("part2",  os.path.join(JC, r"Track2_Part2_profiles\shards")),
]
RECOVERED = [os.path.join(JC, f) for f in ("Recovered_track1_profiles.csv", "Recovered_track2_profiles.csv", "Recovered_part2_profiles.csv")]
WORKERS = 10
SLUG2CO = None


def nrm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def load_slug2co():
    m = {}
    for r in csv.DictReader(open(MASTER_CSV, encoding="utf-8")):
        comp = r["company"]
        for s in (r.get("slugs") or "").split("|"):
            s = s.strip().lower()
            if s:
                m[s] = comp
    return m


def init():
    global SLUG2CO
    SLUG2CO = load_slug2co()


def slugs_of(c):
    out = set()
    u = c.get("lnkd_uid")
    if u:
        out.add(str(u).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        v = c.get(k)
        if v and "/company/" in v:
            s = v.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s:
                out.add(s)
    return out


def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v, list) else []
    except Exception:
        return []


def opener(path):
    return gzip.open(path, "rt", encoding="utf-8", newline="") if path.endswith(".gz") else open(path, "rt", encoding="utf-8", newline="")


def worker(args):
    tk, path = args
    ever = defaultdict(Counter); cur = defaultdict(Counter)   # company -> city -> count
    with opener(path) as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            city = P2.canon_city(((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower()) or "(unknown)"
            comps_ever = set(); comps_cur = set()
            for e in parse(row.get("experience")):
                if not isinstance(e, dict):
                    continue
                hit = slugs_of(e.get("company") or {}) & SLUG2CO.keys()
                if not hit:
                    continue
                dur = e.get("duration") or {}
                isc = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                for comp in {SLUG2CO[s] for s in hit}:
                    comps_ever.add(comp)
                    if isc:
                        comps_cur.add(comp)
            for comp in comps_ever:
                ever[comp][city] += 1
            for comp in comps_cur:
                cur[comp][city] += 1
    return ever, cur


def gcc_city_cols():
    wb = openpyxl.load_workbook(GCC_XLSX, read_only=True, data_only=True)
    ws = wb["GCC Master List"]; rows = list(ws.iter_rows(values_only=True)); hdr = rows[3]
    idx = {str(h).strip(): i for i, h in enumerate(hdr) if h is not None}
    cN = idx["Company Name"]; cU = idx["LinkedIn Entity URL(s)"]
    # city headcount columns -> our canon city name
    citymap = {"Bengaluru Headcount": "bengaluru", "Hyderabad Headcount": "hyderabad", "Pune Headcount": "pune",
               "Mumbai MMR Headcount": "mumbai mmr", "Chennai Headcount": "chennai",
               "Delhi NCR Total Headcount": "delhi ncr", "Kolkata Headcount": "kolkata",
               "Ahmedabad & GIFT City Headcount": "ahmedabad", "Coimbatore Headcount": "coimbatore",
               "Kochi Headcount": "kochi", "Thiruvananthapuram Headcount": "trivandrum", "Jaipur Headcount": "jaipur",
               "Indore Headcount": "indore", "Nagpur Headcount": "nagpur", "Visakhapatnam Headcount": "visakhapatnam",
               "Bhubaneswar Headcount": "bhubaneswar", "Mysuru Headcount": "mysuru"}
    ccols = {idx[k]: v for k, v in citymap.items() if k in idx}
    slug2conf = {}; name2conf = {}
    for r in rows[4:]:
        if not r or not r[cN]:
            continue
        conf = set()
        for ci, cname in ccols.items():
            val = r[ci]
            try:
                if val is not None and float(str(val).replace(",", "").split("-")[0] or 0) > 0:
                    conf.add(cname)
            except Exception:
                if val and str(val).strip() and str(val).strip() not in ("0", "-", "", "0.0"):
                    conf.add(cname)
        sl = set(re.findall(r"/(?:company|showcase)/([^/?#\s,]+)", str(r[cU] or "").lower()))
        for s in sl:
            slug2conf[s] = conf
        name2conf[nrm(r[cN])] = conf
    return slug2conf, name2conf


def main():
    init()
    masters = list(csv.DictReader(open(MASTER_CSV, encoding="utf-8")))
    ind = {m["company"]: (m.get("industry_L1", ""), m.get("industry_L2", ""), m.get("slugs", "")) for m in masters}
    tasks = []
    for tk, d in INPUTS:
        for p in sorted(glob.glob(os.path.join(d, "*.csv.gz"))):
            tasks.append((tk, p))
    for rp in RECOVERED:
        if os.path.exists(rp):
            tasks.append(("rec", rp))
    print(f"centre mapping: {len(tasks)} inputs | workers {WORKERS}", flush=True)
    EVER = defaultdict(Counter); CUR = defaultdict(Counter); t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ev, cu in pool.imap_unordered(worker, tasks):
            for comp, c in ev.items():
                EVER[comp].update(c)
            for comp, c in cu.items():
                CUR[comp].update(c)
    slug2conf, name2conf = gcc_city_cols()
    rows_out = []
    for comp in sorted(EVER, key=lambda c: -sum(EVER[c].values())):
        l1, l2, slugs = ind.get(comp, ("", "", ""))
        conf = set()
        for s in [x.strip().lower() for x in slugs.split("|") if x.strip()]:
            conf |= slug2conf.get(s, set())
        if not conf:
            conf = name2conf.get(nrm(comp), set())
        cities = EVER[comp]
        centres = sorted(cities, key=lambda c: -cities[c])
        total_ever = sum(cities.values()); total_cur = sum(CUR[comp].values())
        centre_detail = "; ".join(f"{c}:{cities[c]:,}(cur {CUR[comp].get(c,0):,})" for c in centres if c != "(unknown)")
        confirmed = [c for c in centres if c in conf and c != "(unknown)"]
        profile_only = [c for c in centres if c not in conf and c != "(unknown)" and cities[c] >= 10]
        rows_out.append({
            "company": comp, "industry_L1": l1, "industry_L2": l2,
            "total_profiles_ever": total_ever, "total_profiles_current": total_cur,
            "n_centres(profile>=10)": len([c for c in centres if c != "(unknown)" and cities[c] >= 10]),
            "confirmed_centres(in_GCC_master)": " | ".join(confirmed),
            "profile_only_centres(flag)": " | ".join(profile_only),
            "centre_detail_city:ever(cur)": centre_detail,
            "evidence": "confirmed+profile" if confirmed else ("profile_only" if total_ever else "none"),
        })
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()), quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(rows_out)
    # companies seen in data but NOT in master (to add)
    inmaster = set(ind)
    extra = [c for c in EVER if c not in inmaster]
    print(f"\n==== CENTRE MAPPING ({time.time()-t0:,.0f}s) ====")
    print(f"  companies with profiles: {len(EVER):,} | rows written: {len(rows_out):,}")
    print(f"  companies in data but NOT in master: {len(extra)}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
