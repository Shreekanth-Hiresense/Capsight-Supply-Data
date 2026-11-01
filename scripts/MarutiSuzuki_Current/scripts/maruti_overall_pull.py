# Purpose: Maruti Suzuki OVERALL (ever-worked) deliverable. Keep every profile with ANY role (past or present)
#   at one of the 4 Maruti slugs AND whose profile location is in the 3 areas (Greater Delhi / Bengaluru /
#   Pune-PCMC). NO currently-working filter, NO 11-function filter (overall is never function-filtered).
#   Writes 32 original columns, QUOTE_ALL, dedup by uid (newest folder wins). Read-only on the dump.
import csv, glob, gzip, os, shutil, sys, time
from collections import Counter
from multiprocessing import Pool
import orjson

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS
from disk_guard import check_disk, estimate_csv_gb, warn_after_write

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(2 ** 31 - 1)
ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_overall_3areas.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\maruti_ever_parts"
WORKERS = 12
SLUGS = {"maruti-udyog-limited", "maruti-suzuki-innovation",
         "suzuki-research-and-development-center-india", "suzuki-digital-private-limited"}
PRE = tuple(s.encode() for s in SLUGS)
COLS = [c for c in OUTPUT_COLUMNS if c != "matched_company_slug"]
AREAS = {
    "Greater Delhi Area": ["greater delhi area", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad",
                           "faridabad", "manesar", "kharkhoda", "sonipat", "bahadurgarh"],
    "Greater Bengaluru Area": ["greater bengaluru area", "bengaluru", "bangalore"],
    "Pune/PCMC Area": ["pune/pimpri-chinchwad area", "pune", "pimpri", "chinchwad"],
}


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


def area_of(addr):
    a = (addr or "").lower()
    for name, toks in AREAS.items():
        if any(t in a for t in toks):
            return name
    return None


def pool_date(path):
    for part in path.replace("/", "\\").split("\\"):
        if part.startswith("ziplabs_passive_IN_"):
            return part.rsplit("_", 1)[-1]
    return "00000000"


def worker(path):
    out = os.path.join(TMP, pool_date(path) + "__" + os.path.basename(path) + ".csv")
    per = Counter()
    fh = open(out, "w", encoding="utf-8", newline="")
    w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore", quoting=csv.QUOTE_ALL)
    with gzip.open(path, "rb") as f:
        for line in f:
            if not any(p in line for p in PRE):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            ever = any((slugs_of(e.get("company") or {}) & SLUGS) for e in (d.get("experience") or []))
            if not ever:
                continue
            addr = ((d.get("miniprofile") or {}).get("location") or {}).get("address")
            ar = area_of(addr)
            if ar is None:
                per["(other-location excluded)"] += 1
                continue
            per[ar] += 1
            r = row_for(d, None)
            r.pop("matched_company_slug", None)
            w.writerow(r)
    fh.close()
    return out, per


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"EVER-worked | slugs {SLUGS}\nshards {len(shards)} | workers {WORKERS}", flush=True)
    parts = []; PER = Counter(); t0 = time.time()
    with Pool(WORKERS) as pool:
        for out, per in pool.imap_unordered(worker, shards):
            parts.append(out); PER.update(per)
    kept_raw = sum(v for k, v in PER.items() if k != "(other-location excluded)")
    check_disk(estimate_csv_gb(kept_raw), label="Maruti overall 3-area")
    parts.sort(reverse=True)
    seen = set(); AREA = Counter(); written = 0
    ai = COLS.index("miniprofile_location_address")
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(COLS)
        for p in parts:
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for row in csv.reader(fi):
                    if not row:
                        continue
                    if row[0] in seen:
                        continue
                    seen.add(row[0]); w.writerow(row); written += 1
                    AREA[area_of(row[ai])] += 1
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n==== DONE ({time.time()-t0:,.0f}s) ====  EVER-worked, 3 areas, no function filter")
    for name in AREAS:
        print(f"  {name:28s} {AREA.get(name,0):>7,}")
    print(f"  TOTAL distinct ever (3 areas): {written:,}")
    print(f"  (other-location excluded: {PER.get('(other-location excluded)',0):,})")
    print(f"  columns {len(COLS)} -> {OUT}")
    warn_after_write(OUT)


if __name__ == "__main__":
    main()
