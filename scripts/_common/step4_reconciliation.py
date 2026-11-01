# Purpose: STEP 4 - final location + target reconciliation for the GCC validation project.
#   Scans the already-pulled track shards (Track1/Track2 shards_min20conn + Part-2 shards + Recovered_*.csv)
#   ONCE and reconciles our numbers against the GCC-master targets (minimum benchmarks), fixing the three
#   things the old keyword-calibration got wrong:
#     1) INDUSTRY (L1/L2) now comes from the VALIDATED GCC-master mapping (Company_Master_List_industry.csv),
#        joined by exact L1/L2 name (GCC names == target names), NOT the old keyword classifier.
#     2) L1/L2 counts are DISTINCT UIDs per category (a person at two BFSI companies counts once in BFSI),
#        so there is no cross-company double-counting.
#     3) LOCATION: Delhi-NCR stays GROUPED and is reported as ONE line vs the combined Gurugram+Noida+Delhi
#        target; city coverage is EXPANDED so the tier-2/3 targets that canon_city never recognised
#        (Vadodara, Panaji & Goa, Udupi, Aurangabad, Madurai, Vijayawada, Mangaluru, Lucknow, Shillong,
#        Belagavi, Guwahati, Hubballi, Tumakuru, Shivamogga, Karwar) are now mapped instead of dropped.
#   "Currently working" = Jani logic (present OR start-and-no-end). Part-2 companies' CURRENT is restricted
#   to the 11-function uid set (PART2_IN11); Track-1/Track-2 current = Jani unrestricted. One row per distinct
#   uid for city/state; distinct uid per L1/L2. READ-ONLY on all sources; writes only to Jani Capsight.
import ast, csv, glob, gzip, os, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1); sys.stdout.reconfigure(encoding="utf-8", errors="replace")
JC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
MASTER_CSV = os.path.join(JC, "Company_Master_List_industry.csv")
TGT_CSV = os.path.join(JC, "Calibration_targets.csv")
IN11_TXT = os.path.join(JC, "part2_in11_uids.txt")
OUT = os.path.join(JC, "Calibration_match_GCCmaster.csv")
NOTES = os.path.join(JC, "Step4_reconciliation_notes.txt")
INPUTS = [
    os.path.join(JC, r"Track1_BySlug_profiles\shards_min20conn"),
    os.path.join(JC, r"Track2_BySlug_profiles\shards_min20conn"),
    os.path.join(JC, r"Track2_Part2_profiles\shards"),
]
RECOVERED = [os.path.join(JC, f) for f in ("Recovered_track1_profiles.csv", "Recovered_track2_profiles.csv", "Recovered_part2_profiles.csv")]
WORKERS = 10

# --- EXPANDED city aliases (adds every target city canon_city used to miss). order: specific before generic ---
CITY = [
    ("delhi ncr", ["new delhi", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad", "greater noida"]),
    ("mumbai mmr", ["navi mumbai", "mumbai", "thane", "kalyan", "vasai"]),
    ("bengaluru", ["bengaluru", "bangalore"]),
    ("hyderabad", ["hyderabad", "secunderabad"]),
    ("chennai", ["chennai"]), ("pune", ["pune"]), ("kolkata", ["kolkata"]),
    ("ahmedabad", ["ahmedabad", "gandhinagar", "gift city"]), ("coimbatore", ["coimbatore"]),
    ("visakhapatnam", ["visakhapatnam", "vizag"]),
    ("jaipur", ["jaipur"]), ("chandigarh", ["chandigarh", "mohali", "panchkula"]), ("kochi", ["kochi", "cochin", "ernakulam"]),
    ("indore", ["indore"]), ("nagpur", ["nagpur"]), ("trivandrum", ["thiruvananthapuram", "trivandrum"]),
    ("bhubaneswar", ["bhubaneswar"]), ("mysuru", ["mysuru", "mysore"]),
    # --- expanded tier-2/3 (previously 0% because canon_city had no alias) ---
    ("vadodara", ["vadodara", "baroda"]), ("panaji goa", ["panaji", "panjim", "margao", "madgaon", "vasco", "mapusa", "goa"]),
    ("udupi manipal", ["udupi", "manipal"]), ("aurangabad", ["aurangabad", "sambhaji nagar", "chhatrapati sambhaji"]),
    ("madurai", ["madurai"]), ("vijayawada", ["vijayawada", "bezawada"]), ("mangaluru", ["mangaluru", "mangalore"]),
    ("lucknow", ["lucknow"]), ("shillong", ["shillong"]), ("belagavi", ["belagavi", "belgaum"]),
    ("guwahati", ["guwahati", "gauhati"]), ("hubballi dharwad", ["hubballi", "hubli", "dharwad"]),
    ("tumakuru", ["tumakuru", "tumkur"]), ("shivamogga", ["shivamogga", "shimoga"]), ("karwar", ["karwar"]),
]
def canon_city(addr):
    t = (addr or "").lower()
    for canon, al in CITY:
        for a in al:
            if a in t:
                return canon
    return None

# canon city -> target CITY name (1:1; delhi ncr is one grouped line)
CANON2CITYTGT = {
    "bengaluru": "Bengaluru", "hyderabad": "Hyderabad", "chennai": "Chennai", "pune": "Pune",
    "mumbai mmr": "Mumbai MMR", "delhi ncr": "Delhi-NCR (Gurugram+Noida+Delhi)", "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad & GIFT City", "coimbatore": "Coimbatore", "vadodara": "Vadodara", "kochi": "Kochi",
    "trivandrum": "Thiruvananthapuram", "jaipur": "Jaipur", "indore": "Indore", "chandigarh": "Chandigarh Tricity",
    "bhubaneswar": "Bhubaneswar", "nagpur": "Nagpur", "visakhapatnam": "Visakhapatnam", "panaji goa": "Panaji & Goa",
    "mysuru": "Mysuru", "udupi manipal": "Udupi & Manipal", "aurangabad": "Chhatrapati Sambhaji Nagar (Aurangabad)",
    "madurai": "Madurai", "vijayawada": "Vijayawada", "mangaluru": "Mangaluru", "lucknow": "Lucknow",
    "shillong": "Shillong", "belagavi": "Belagavi", "guwahati": "Guwahati", "hubballi dharwad": "Hubballi & Dharwad",
    "tumakuru": "Tumakuru (Tumkur)", "shivamogga": "Shivamogga", "karwar": "Karwar",
}
# canon city -> state (delhi ncr kept as its own grouped "state")
CANON2STATE = {
    "bengaluru": "Karnataka", "mysuru": "Karnataka", "mangaluru": "Karnataka", "udupi manipal": "Karnataka",
    "belagavi": "Karnataka", "hubballi dharwad": "Karnataka", "tumakuru": "Karnataka", "shivamogga": "Karnataka",
    "karwar": "Karnataka", "hyderabad": "Telangana", "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu",
    "madurai": "Tamil Nadu", "pune": "Maharashtra", "mumbai mmr": "Maharashtra", "nagpur": "Maharashtra",
    "aurangabad": "Maharashtra", "delhi ncr": "Delhi-NCR (grouped)", "kolkata": "West Bengal",
    "ahmedabad": "Gujarat", "vadodara": "Gujarat", "kochi": "Kerala", "trivandrum": "Kerala",
    "jaipur": "Rajasthan", "indore": "Madhya Pradesh", "chandigarh": "Punjab / Haryana / UT",
    "bhubaneswar": "Odisha", "visakhapatnam": "Andhra Pradesh", "vijayawada": "Andhra Pradesh",
    "panaji goa": "Goa", "lucknow": "Uttar Pradesh", "shillong": "Meghalaya", "guwahati": "Assam",
}

SLUG2CO = None; IND = None; PART2_COMPS = None; PART2_IN11 = None


def nrm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def load_shared():
    slug2co = {}; ind = {}; p2 = set()
    for r in csv.DictReader(open(MASTER_CSV, encoding="utf-8")):
        comp = r["company"]
        ind[comp] = (r.get("industry_L1", "") or "", r.get("industry_L2", "") or "")
        if "part2" in (r.get("tracks") or ""):
            p2.add(comp)
        for s in (r.get("slugs") or "").split("|"):
            s = s.strip().lower()
            if s:
                slug2co[s] = comp
    in11 = set()
    if os.path.exists(IN11_TXT):
        with open(IN11_TXT, encoding="utf-8") as fh:
            in11 = set(line.strip() for line in fh if line.strip())
    return slug2co, ind, p2, in11


def init():
    global SLUG2CO, IND, PART2_COMPS, PART2_IN11
    SLUG2CO, IND, PART2_COMPS, PART2_IN11 = load_shared()


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


def worker(path):
    own_by_uid = {}            # uid -> own canon city   (only for uids currently working at a target co)
    l1_pairs = set(); l2_pairs = set()   # (uid, L1) / (uid, L2) distinct
    cur_uids = set()
    with opener(path) as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            uid = row.get("uid")
            own = canon_city(((row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")).lower())
            cur_comps = set()
            for e in parse(row.get("experience")):
                if not isinstance(e, dict):
                    continue
                hit = slugs_of(e.get("company") or {}) & SLUG2CO.keys()
                if not hit:
                    continue
                dur = e.get("duration") or {}
                isc = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if not isc:
                    continue
                for comp in {SLUG2CO[s] for s in hit}:
                    if comp in PART2_COMPS and uid not in PART2_IN11:
                        continue   # Part-2 current kept only if in the 11 functions
                    cur_comps.add(comp)
            if not cur_comps:
                continue
            cur_uids.add(uid)
            own_by_uid[uid] = own or ""
            for comp in cur_comps:
                l1, l2 = IND.get(comp, ("", ""))
                if l1:
                    l1_pairs.add((uid, l1))
                if l2:
                    l2_pairs.add((uid, l2))
    return own_by_uid, l1_pairs, l2_pairs, cur_uids


def main():
    init()
    tgt = {"L1": {}, "L2": {}, "CITY": {}, "STATE": {}}
    for r in csv.DictReader(open(TGT_CSV, encoding="utf-8")):
        tgt[r["level"]][r["name"]] = int(r["calibrated_talent"])
    # --- Delhi-NCR grouping adjustments (keep grouped; fold sub-targets into one benchmark) ---
    city_tgt = dict(tgt["CITY"])
    ncr = city_tgt.pop("Gurugram", 0) + city_tgt.pop("Noida", 0) + city_tgt.pop("Delhi", 0)
    city_tgt["Delhi-NCR (Gurugram+Noida+Delhi)"] = ncr
    state_tgt = dict(tgt["STATE"])
    ncr_state = state_tgt.pop("Haryana", 0) + state_tgt.pop("NCT of Delhi", 0) + 81825  # + Noida share of UP
    state_tgt["Delhi-NCR (grouped)"] = ncr_state
    if "Uttar Pradesh" in state_tgt:
        state_tgt["Uttar Pradesh"] = state_tgt["Uttar Pradesh"] - 81825   # UP remainder = Lucknow

    tasks = []
    for d in INPUTS:
        tasks += sorted(glob.glob(os.path.join(d, "*.csv.gz")))
    tasks += [p for p in RECOVERED if os.path.exists(p)]
    print(f"step4 reconciliation: {len(tasks)} inputs | workers {WORKERS}", flush=True)
    OWN = {}; L1P = set(); L2P = set(); CUR = set(); t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for own_by_uid, l1p, l2p, cur in pool.imap_unordered(worker, tasks):
            OWN.update(own_by_uid); L1P |= l1p; L2P |= l2p; CUR |= cur
    # distinct-uid aggregates
    city_c = Counter(); state_c = Counter()
    for uid in CUR:
        c = OWN.get(uid, "")
        city_c[c] += 1
        state_c[CANON2STATE.get(c, "other/unknown")] += 1
    l1_c = Counter(); l2_c = Counter()
    for _, l1 in L1P:
        l1_c[l1] += 1
    for _, l2 in L2P:
        l2_c[l2] += 1
    # our city count by target name
    ourcity = Counter()
    for canon, n in city_c.items():
        nm = CANON2CITYTGT.get(canon)
        if nm:
            ourcity[nm] += n

    rows = [["LEVEL", "name", "ours_current_distinct", "target_min", "our/target %", "status"]]

    def emit(lvl, ours_map, tgt_map):
        print(f"\n-- {lvl} --")
        for name in sorted(tgt_map, key=lambda k: -tgt_map[k]):
            t = tgt_map[name]; ours = ours_map.get(name, 0)
            pct = (100 * ours / t) if t else 0
            st = "OK (>=target)" if ours >= t else ("SHORTFALL" if ours < 0.9 * t else "near")
            rows.append([lvl, name, ours, t, round(pct, 1), st])
            print(f"   {name[:46]:46s} ours {ours:>9,} | target {t:>9,} | {pct:5.0f}%  {st}")

    print(f"\n==== STEP-4 RECONCILIATION (currently-working Jani; Part-2 current=in-11; GCC-master industries) ====")
    print(f"distinct current uids across all tracks: {len(CUR):,}")
    emit("L1", l1_c, tgt["L1"])
    emit("L2", l2_c, tgt["L2"])
    emit("STATE", state_c, state_tgt)
    emit("CITY", ourcity, city_tgt)
    # unmapped own-city share (profiles whose own location did not resolve to any target city)
    unmapped = city_c.get("", 0)
    print(f"\n  current uids with UNRESOLVED own city (not any target city): {unmapped:,} ({100*unmapped/max(1,len(CUR)):.1f}%)")
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)

    # ---- notes / corrections writeup (Step 5 seed) ----
    with open(NOTES, "w", encoding="utf-8") as fh:
        fh.write("STEP 4 - LOCATION + TARGET RECONCILIATION NOTES\n")
        fh.write(f"generated {time.strftime('%Y-%m-%d %H:%M:%S')} | scan {time.time()-t0:,.0f}s\n\n")
        fh.write("CORRECTIONS APPLIED vs the earlier keyword-calibration:\n")
        fh.write("  1. Industry (L1/L2) now from the VALIDATED GCC-master mapping (Company_Master_List_industry.csv),\n")
        fh.write("     joined by exact L1/L2 name. The earlier run used a keyword classifier (approximate).\n")
        fh.write("  2. L1/L2 counts are DISTINCT uids per category (no cross-company double-count).\n")
        fh.write("  3. Delhi-NCR kept GROUPED: reported as ONE city line vs combined Gurugram+Noida+Delhi target\n")
        fh.write(f"     (combined city target {ncr:,}); state folded into 'Delhi-NCR (grouped)' (target {ncr_state:,}).\n")
        fh.write("  4. City coverage EXPANDED: Vadodara, Panaji & Goa, Udupi & Manipal, Aurangabad, Madurai,\n")
        fh.write("     Vijayawada, Mangaluru, Lucknow, Shillong, Belagavi, Guwahati, Hubballi & Dharwad, Tumakuru,\n")
        fh.write("     Shivamogga, Karwar now mapped (canon_city previously dropped them to blank).\n\n")
        fh.write("TARGETS ARE MINIMUM BENCHMARKS: ours >= target = OK (no action). ours < target = shortfall to explain.\n\n")
        fh.write("SHORTFALLS (ours < target) to investigate for genuine gaps vs missing companies:\n")
        for lvl, mp in (("CITY", (ourcity, city_tgt)), ("STATE", (state_c, state_tgt)), ("L1", (l1_c, tgt["L1"])), ("L2", (l2_c, tgt["L2"]))):
            om, tm = mp
            for name in sorted(tm, key=lambda k: -tm[k]):
                t = tm[name]; o = om.get(name, 0)
                if t and o < t:
                    fh.write(f"  [{lvl}] {name}: {o:,} / {t:,} ({100*o/t:.0f}%)\n")
        fh.write(f"\nUnresolved own-city current uids: {unmapped:,} ({100*unmapped/max(1,len(CUR)):.1f}%) - these sit in no target city;\n")
        fh.write("  mostly genuinely smaller towns outside the 34 benchmark cities (expected, India-wide pool).\n")
    print(f"\n  -> {OUT}\n  -> {NOTES}")


if __name__ == "__main__":
    main()
