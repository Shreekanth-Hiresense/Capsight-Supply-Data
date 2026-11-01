# Purpose: Standalone Toyota INDIA deliverable (like Maruti). Pull profiles with any role at the real Toyota
#   India entity pages, restricted to locations Bengaluru + Chennai (metro-grouped). Report ever-worked and
#   currently-working (Jani) by city; write the currently-working profiles (32 original cols) to CSV. Read-only
#   on the dump; dedup by uid (newest folder wins). NOTE: excludes the global 'toyota' page (that's Track-2).
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
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Toyota_India_current_blr_chennai.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\toyota_parts"
WORKERS = 12
SLUGS = {"toyota-kirloskar-motor", "toyota-connected-india-pvt-ltd"}
PRE = (b"toyota",)
COLS = [c for c in OUTPUT_COLUMNS if c != "matched_company_slug"]
BLR = ["bengaluru", "bangalore"]
CHE = ["chennai"]


def city_of(addr):
    a = (addr or "").lower()
    if any(t in a for t in BLR):
        return "bengaluru"
    if any(t in a for t in CHE):
        return "chennai"
    return None


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


def pool_date(path):
    for part in path.replace("/", "\\").split("\\"):
        if part.startswith("ziplabs_passive_IN_"):
            return part.rsplit("_", 1)[-1]
    return "0"


def worker(path):
    out = os.path.join(TMP, pool_date(path) + "__" + os.path.basename(path) + ".csv")
    fh = open(out, "w", encoding="utf-8", newline="")
    w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    ever = Counter(); cur = Counter()
    with gzip.open(path, "rb") as f:
        for line in f:
            if not any(p in line for p in PRE):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            is_ever = False; is_cur = False
            for e in d.get("experience") or []:
                if not (slugs_of(e.get("company") or {}) & SLUGS):
                    continue
                is_ever = True
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    is_cur = True
            if not is_ever:
                continue
            city = city_of(((d.get("miniprofile") or {}).get("location") or {}).get("address"))
            if city is None:
                continue
            ever[city] += 1
            if is_cur:
                cur[city] += 1
                r = row_for(d, None); r.pop("matched_company_slug", None)
                w.writerow([r.get(c, "") for c in COLS] + [d.get("uid")])  # last col = uid tag for dedup
    fh.close()
    return out, ever, cur


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"Toyota India slugs {len(SLUGS)} | shards {len(shards)} | locations: bengaluru, chennai", flush=True)
    parts = []; EVER = Counter(); CUR = Counter(); t0 = time.time()
    with Pool(WORKERS) as pool:
        for out, ev, cu in pool.imap_unordered(worker, shards):
            parts.append(out); EVER.update(ev); CUR.update(cu)
    check_disk(estimate_csv_gb(sum(CUR.values())), label="Toyota India current")
    parts.sort(reverse=True)
    seen = set(); written = 0; CUR_D = Counter()
    ci = COLS.index("miniprofile_location_address")
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(COLS)
        for p in parts:
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for row in csv.reader(fi):
                    if not row:
                        continue
                    uid = row[-1]
                    if uid in seen:
                        continue
                    seen.add(uid); w.writerow(row[:-1]); written += 1
                    CUR_D[city_of(row[ci])] += 1
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n==== Toyota India ({time.time()-t0:,.0f}s) ====  (raw per-shard counts; CSV dedup by uid)")
    print(f"  {'city':12s} {'ever':>8} {'current(Jani)':>14}")
    for c in ("bengaluru", "chennai"):
        print(f"  {c:12s} {EVER.get(c,0):>8,} {CUR.get(c,0):>14,}")
    print(f"  {'TOTAL':12s} {sum(EVER.values()):>8,} {sum(CUR.values()):>14,}")
    print(f"  CSV (current, distinct uid): {written:,} rows -> {OUT}")
    print(f"  current distinct by city: {dict(CUR_D)}")
    warn_after_write(OUT)


if __name__ == "__main__":
    main()
