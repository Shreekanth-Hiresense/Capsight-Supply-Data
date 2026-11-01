
# PILOT: company-first centre-by-centre coverage for 6 GCC companies.
# For each company: scan our pulled profiles (all track sources), keep CURRENT (Jani) roles at the
# company's VALIDATED slug set (pollution removed), map each person to their ACTUAL WORKING LOCATION
# (role location first, else profile location), group Delhi-NCR, tally distinct uids per centre, and
# compare to the GCC-master per-centre headcount. Emits coverage + per-slug validation. READ-ONLY sources.
import ast, csv, glob, gzip, os, re, sys, time
from collections import defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1); sys.stdout.reconfigure(encoding="utf-8", errors="replace")
JC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
OUTDIR = os.path.dirname(os.path.abspath(__file__))
INPUTS = [
    os.path.join(JC, r"Track1_BySlug_profiles\shards_min20conn"),
    os.path.join(JC, r"Track2_BySlug_profiles\shards_min20conn"),
    os.path.join(JC, r"Track2_Part2_profiles\shards"),
]
RECOVERED = [os.path.join(JC, f) for f in ("Recovered_track1_profiles.csv", "Recovered_track2_profiles.csv", "Recovered_part2_profiles.csv")]
WORKERS = 10

# --- validated slug sets (company-first; pollution excluded) ---
ALLOW = {
    "Standard Chartered": {"standardchartered", "standard-chartered-india"},
    "Ford Motor Company": {"ford-motor-company", "ford-motor-companyx", "fordchina"},
    "Caterpillar": {"caterpillar-inc", "caterpillar-india-pvt-ltd"},
    "Target Corporation": {"target"},
    "Zoho Corporation": {"zoho", "zoho-backstage", "zohorecruit"},
    "Omega Healthcare": {"omega-healthcare-management-services"},
}
# slugs we deliberately DROP (to measure pollution volume, not credited)
DROP = {
    "Standard Chartered": {"astrazeneca", "astrazeneca-taiwan", "astrazenecaindia"},
    "Caterpillar": {"construction-ai"},
    "Target Corporation": {"target-engineering-construction-co-llc", "target-retail-ltd"},
}
SLUG2CO = {}; SLUG2KIND = {}   # slug -> company ; slug -> 'keep'/'drop'
for co, ss in ALLOW.items():
    for s in ss: SLUG2CO[s] = co; SLUG2KIND[s] = "keep"
for co, ss in DROP.items():
    for s in ss: SLUG2CO[s] = co; SLUG2KIND[s] = "drop"

# --- GCC-master per-centre headcount (from gcc master list (2).xlsx; Delhi-NCR grouped) ---
MASTER_HC = {
    "Standard Chartered": {"Bengaluru": 5501, "Chennai": 2497, "Ahmedabad & GIFT City": 717, "Mumbai MMR": 628, "Pune": 565, "Delhi NCR": 560, "Hyderabad": 376, "Kolkata": 355},
    "Ford Motor Company": {"Chennai": 4395, "Bengaluru": 942, "Coimbatore": 533},
    "Caterpillar": {"Bengaluru": 2379, "Chennai": 1780},
    "Omega Healthcare": {"Hyderabad": 10074},
    "Target Corporation": {"Bengaluru": 3724},
    "Zoho Corporation": {"Bengaluru": 154},
}
MASTER_TOTAL = {"Standard Chartered": 11199, "Ford Motor Company": 5870, "Caterpillar": 4159,
                "Omega Healthcare": 10074, "Target Corporation": 3724, "Zoho Corporation": 154}
# master-authoritative page we did NOT pull (flag)
MISSING_MASTER_PAGE = {"Target Corporation": "target-in-india", "Omega Healthcare": "omega-healthcare", "Caterpillar": "caterpillar-inc- (trailing dash)"}

# canon city -> master city label
CITY = [
    ("Delhi NCR", ["new delhi", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad", "greater noida"]),
    ("Mumbai MMR", ["navi mumbai", "mumbai", "thane", "kalyan", "vasai"]),
    ("Bengaluru", ["bengaluru", "bangalore"]), ("Hyderabad", ["hyderabad", "secunderabad"]),
    ("Chennai", ["chennai"]), ("Pune", ["pune"]), ("Kolkata", ["kolkata"]),
    ("Ahmedabad & GIFT City", ["ahmedabad", "gandhinagar", "gift city"]), ("Coimbatore", ["coimbatore"]),
    ("Visakhapatnam", ["visakhapatnam", "vizag"]), ("Jaipur", ["jaipur"]),
    ("Chandigarh Tricity", ["chandigarh", "mohali", "panchkula"]), ("Kochi", ["kochi", "cochin", "ernakulam"]),
    ("Indore", ["indore"]), ("Nagpur", ["nagpur"]), ("Thiruvananthapuram", ["thiruvananthapuram", "trivandrum"]),
    ("Bhubaneswar", ["bhubaneswar"]), ("Mysuru", ["mysuru", "mysore"]), ("Madurai", ["madurai"]),
    ("Tiruchirappalli", ["tiruchirappalli", "trichy"]), ("Vadodara", ["vadodara", "baroda"]),
]
def canon_city(addr):
    t = (addr or "").lower()
    for canon, al in CITY:
        for a in al:
            if a in t:
                return canon
    return None

def slugs_of(c):
    out = set()
    u = c.get("lnkd_uid")
    if u: out.add(str(u).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        v = c.get(k)
        if v and "/company/" in v:
            s = v.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s: out.add(s)
    return out

def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v, list) else []
    except Exception:
        return []

def opener(path):
    return gzip.open(path, "rt", encoding="utf-8", newline="") if path.endswith(".gz") else open(path, "rt", encoding="utf-8", newline="")

ALLSET = set(SLUG2CO.keys())

def worker(path):
    # per (company, centre) distinct uids ; per slug distinct uids + sample names ; working-loc source counts
    cc = defaultdict(set)              # (company, centre) -> uids   (keep slugs only, current)
    slug_uids = defaultdict(set)       # slug -> uids (current, any)
    slug_names = defaultdict(lambda: defaultdict(int))  # local only; converted to plain dict before return
    locsrc = defaultdict(int)          # company -> {'role','profile','none'} counts (keep, current)
    with opener(path) as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            uid = row.get("uid")
            prof_loc = ((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower()
            # gather this person's current roles at our slugs
            hits = []   # (company, kind, role_location_str, name)
            for e in parse(row.get("experience")):
                if not isinstance(e, dict): continue
                comp_obj = e.get("company") or {}
                if not isinstance(comp_obj, dict): continue
                sl = slugs_of(comp_obj) & ALLSET
                if not sl: continue
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if not is_cur: continue
                rloc = e.get("location") or ""
                nm = (comp_obj.get("name") or "")
                for s in sl:
                    hits.append((s, SLUG2CO[s], SLUG2KIND[s], rloc, nm))
            if not hits:
                continue
            for s, co, kind, rloc, nm in hits:
                slug_uids[s].add(uid)
                if nm: slug_names[s][nm[:40]] += 1
            # credit KEEP slugs to centre by working location (role loc first, else profile)
            for co in {h[1] for h in hits if h[2] == "keep"}:
                # pick a role location for this company (first non-empty role loc among its keep roles)
                rlocs = [h[3] for h in hits if h[1] == co and h[2] == "keep" and h[3]]
                if rlocs:
                    centre = None
                    for rl in rlocs:
                        centre = canon_city(rl)
                        if centre: break
                    src = "role"
                    if not centre:   # role loc present but unrecognised -> try profile
                        centre = canon_city(prof_loc); src = "profile" if centre else "none"
                else:
                    centre = canon_city(prof_loc); src = "profile" if centre else "none"
                locsrc[(co, src)] += 1
                cc[(co, centre or "UNLOCATED")].add(uid)
    return dict(cc), dict(slug_uids), {k: dict(v) for k, v in slug_names.items()}, dict(locsrc)

def main():
    t0 = time.time()
    tasks = []
    for d in INPUTS:
        tasks += sorted(glob.glob(os.path.join(d, "*.csv.gz")))
    tasks += [p for p in RECOVERED if os.path.exists(p)]
    print(f"pilot scan: {len(tasks)} inputs | workers {WORKERS}", flush=True)
    CC = defaultdict(set); SU = defaultdict(set); SN = defaultdict(lambda: defaultdict(int)); LS = defaultdict(int)
    done = 0
    with Pool(WORKERS) as pool:
        for cc, su, sn, ls in pool.imap_unordered(worker, tasks):
            for k, v in cc.items(): CC[k] |= v
            for k, v in su.items(): SU[k] |= v
            for k, d in sn.items():
                for nm, n in d.items(): SN[k][nm] += n
            for k, v in ls.items(): LS[k] += v
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(tasks)} | {time.time()-t0:.0f}s", flush=True)

    # --- coverage output ---
    cov = os.path.join(OUTDIR, "pilot_centre_coverage.csv")
    with open(cov, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["company", "centre_city", "master_headcount", "our_current_mapped", "coverage_pct", "evidence"])
        for co in ALLOW:
            mh = MASTER_HC.get(co, {})
            # centres present in master
            centres = set(mh.keys()) | {c for (c0, c) in CC if c0 == co}
            # order: master centres by headcount desc, then extras
            ordered = sorted(mh.keys(), key=lambda c: -mh[c]) + sorted(c for c in centres if c not in mh)
            comp_total = 0
            for c in ordered:
                ours = len(CC.get((co, c), set()))
                comp_total += ours
                m = mh.get(c, "")
                if c == "UNLOCATED":
                    ev = "no working location"
                elif c in mh:
                    ev = "confirmed master centre"
                else:
                    ev = "profile-only (not a master centre)"
                pct = (round(100 * ours / m, 1) if isinstance(m, int) and m else "")
                w.writerow([co, c, m, ours, pct, ev])
            # company totals
            mt = MASTER_TOTAL.get(co, "")
            tot_pct = (round(100 * comp_total / mt, 1) if isinstance(mt, int) and mt else "")
            w.writerow([co, "TOTAL (all mapped current)", mt, comp_total, tot_pct, ""])
            if co in MISSING_MASTER_PAGE:
                w.writerow([co, f"!! master page not pulled: {MISSING_MASTER_PAGE[co]}", "", "", "", "coverage likely understated"])
            w.writerow([])

    # --- slug validation output ---
    sv = os.path.join(OUTDIR, "pilot_slug_validation.csv")
    with open(sv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["company", "slug", "decision", "distinct_current_profiles", "top_company_names"])
        for s in sorted(SU, key=lambda s: (SLUG2CO[s], -len(SU[s]))):
            top = sorted(SN[s].items(), key=lambda kv: -kv[1])[:3]
            w.writerow([SLUG2CO[s], s, SLUG2KIND[s], len(SU[s]), "; ".join(f"{n}({c})" for n, c in top)])

    # --- location-source summary ---
    print("\nWORKING-LOCATION SOURCE (keep slugs, current):")
    for co in ALLOW:
        r = LS.get((co, "role"), 0); p = LS.get((co, "profile"), 0); n = LS.get((co, "none"), 0)
        tot = r + p + n
        if tot:
            print(f"  {co:22s} role-loc {r:>6,} ({100*r/tot:.0f}%) | profile-loc {p:>6,} | none {n:>5,} | total {tot:,}")
    print(f"\nDONE {time.time()-t0:.0f}s -> {cov} ; {sv}", flush=True)

if __name__ == "__main__":
    main()
