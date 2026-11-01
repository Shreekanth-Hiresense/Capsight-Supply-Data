# Purpose: Overall (ever-worked) profiles for 5 companies with final_location, + report overall + currently-
#   working (Jani) per company. Companies/slugs are fixed (given by user). Toyota = 2 India pages, primaries
#   FIXED to Bengaluru+Chennai; the other 4 use the tiered cap (>5k=2%/1k-5k=4%/<1k=5%, >=10). One dump scan
#   (small byte prefilter on the 5 names, then exact slug set-check). Writes 32 original cols + company +
#   final_location, one row per (profile x company), >=20 conn, dedup by (uid,company).
import csv, glob, gzip, os, shutil, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
import orjson

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts")
import part2_negation as P2   # for canon_city

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(2 ** 31 - 1)
ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\FiveCompanies_overall_location.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\five_parts"
WORKERS = 12
COLS = [c for c in OUTPUT_COLUMNS if c != "matched_company_slug"]
SLUG2CO = {
    "chase": "JPMorgan Chase", "jpmorgan": "JPMorgan Chase", "jpmorganchase": "JPMorgan Chase",
    "pfizer": "Pfizer", "pfizer-inc": "Pfizer", "pfizer-us": "Pfizer",
    "amd": "AMD", "amd-pensando": "AMD", "amd-research-&-development-india-private-limited": "AMD",
    "walmartglobaltechindia": "Walmart Global Tech", "walmart": "Walmart Global Tech", "walmartglobaltech": "Walmart Global Tech",
    "toyota-kirloskar-motor": "Toyota", "toyota-connected-india-pvt-ltd": "Toyota",
}
PRE = (b"jpmorgan", b"chase", b"pfizer", b"walmart", b"toyota", b"pensando", b"amd")
TOYOTA_FIXED = {"bengaluru", "chennai"}


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


def pooldate(path):
    for part in path.replace("/", "\\").split("\\"):
        if part.startswith("ziplabs_passive_IN_"):
            return part.rsplit("_", 1)[-1]
    return "0"


def worker(path):
    out = os.path.join(TMP, pooldate(path) + "__" + os.path.basename(path) + ".csv")
    fh = open(out, "w", encoding="utf-8", newline=""); w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    ever = Counter(); cur = Counter(); owncity = defaultdict(Counter)
    with gzip.open(path, "rb") as f:
        for line in f:
            if not any(p in line for p in PRE):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            try:
                conn = int((d.get("miniprofile") or {}).get("connections"))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            uid = d.get("uid")
            own = P2.canon_city((((d.get("miniprofile") or {}).get("location") or {}).get("address") or "").lower())
            per = {}   # company -> {ever, cur, curloc, past(set)}
            for e in d.get("experience") or []:
                if not isinstance(e, dict):
                    continue
                hit = slugs_of(e.get("company") or {}) & SLUG2CO.keys()
                if not hit:
                    continue
                comps = {SLUG2CO[s] for s in hit}
                dur = e.get("duration") or {}
                isc = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                rloc = P2.canon_city((e.get("location") or "").lower())
                for comp in comps:
                    pc = per.setdefault(comp, {"ever": True, "cur": False, "curloc": "", "past": set()})
                    if isc:
                        pc["cur"] = True
                        if rloc and not pc["curloc"]:
                            pc["curloc"] = rloc
                    elif rloc:
                        pc["past"].add(rloc)
            if not per:
                continue
            base = row_for(d, None); base.pop("matched_company_slug", None)
            baserow = [base.get(c, "") for c in COLS]
            for comp, pc in per.items():
                ever[comp] += 1
                if pc["cur"]:
                    cur[comp] += 1
                if own:
                    owncity[comp][own] += 1
                w.writerow([comp, uid, own, 1 if pc["cur"] else 0, pc["curloc"], "|".join(sorted(pc["past"]))] + baserow)
    fh.close()
    return out, ever, cur, owncity


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"5-company pull | {len(shards)} shards | workers {WORKERS}", flush=True)
    parts = []; EVER = Counter(); CUR = Counter(); OWN = defaultdict(Counter); t0 = time.time()
    with Pool(WORKERS) as pool:
        for out, ev, cu, oc in pool.imap_unordered(worker, shards):
            parts.append(out); EVER.update(ev); CUR.update(cu)
            for comp, c in oc.items():
                OWN[comp].update(c)
    # primaries per company
    primary = {}
    for comp in EVER:
        if comp == "Toyota":
            primary[comp] = set(TOYOTA_FIXED)
        else:
            tot = EVER[comp]; cc = CUR[comp]
            pct = 0.02 if cc > 5000 else (0.04 if cc >= 1000 else 0.05)
            primary[comp] = {c for c, n in OWN[comp].items() if n >= 10 and n >= pct * tot}
    # merge partials, assign final_location, dedup by (uid,company)
    seen = set(); written = 0; bycity = defaultdict(Counter)
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(COLS + ["company", "final_location"])
        for p in sorted(parts):
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for row in csv.reader(fi):
                    if not row:
                        continue
                    comp, uid, own, isc, curloc, past = row[0], row[1], row[2], row[3], row[4], row[5]
                    key = (uid, comp)
                    if key in seen:
                        continue
                    seen.add(key)
                    prim = primary.get(comp, set())
                    loc = ""
                    if own and own in prim:
                        loc = own
                    elif curloc and curloc in prim:
                        loc = curloc
                    else:
                        h = [x for x in past.split("|") if x and x in prim]
                        loc = h[0] if h else ""
                    w.writerow(row[6:] + [comp, loc]); written += 1
                    if loc:
                        bycity[comp][loc] += 1
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n==== 5-COMPANY ({time.time()-t0:,.0f}s) ====  rows written {written:,} -> {OUT}")
    print(f"  {'company':22s} {'overall(ever)':>14} {'currently(Jani)':>16}")
    for comp in sorted(EVER, key=lambda c: -EVER[c]):
        print(f"  {comp:22s} {EVER[comp]:>14,} {CUR[comp]:>16,}")
    print(f"  {'TOTAL':22s} {sum(EVER.values()):>14,} {sum(CUR.values()):>16,}")
    print("\n  final_location split per company:")
    for comp in sorted(EVER, key=lambda c: -EVER[c]):
        print(f"   {comp}: " + ", ".join(f"{c} {n:,}" for c, n in bycity[comp].most_common()))


if __name__ == "__main__":
    main()
