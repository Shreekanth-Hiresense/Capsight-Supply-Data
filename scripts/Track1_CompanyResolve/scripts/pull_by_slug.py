# Purpose: FINAL pull. Scan passive_IN (read-only) and keep every profile with any experience role at a
#   confirmed Track-1 LinkedIn company SLUG (final_slugs.csv). Slug match = company.lnkd_uid or /company/<slug>
#   in lnkd_url1/url2 -> entity-exact, name-agnostic (catches "J.P. Morgan" people on the jpmorgan page).
#   Output: GZIP SHARDS of all 32 ORIGINAL columns (one row per uid) to Jani Capsight + sidecar uid->matched
#   slugs/companies (so match info stays out of the columns). Resumable per source shard; single instance.
import csv, glob, gzip, io, os, sys, time
from collections import Counter
from multiprocessing import Pool
import orjson

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS  # noqa: E402

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
SLUG_FILE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles"
SHARD_DIR = os.path.join(OUT_DIR, "shards")
SIDE_DIR = os.path.join(OUT_DIR, "_sidecars")
WORKERS = 15
LIMIT = int(os.environ["LIMIT_FILES"]) if os.environ.get("LIMIT_FILES") else None
assert "hiresense_data_ziplabs" not in OUT_DIR

SLUGS = None


def init():
    global SLUGS
    SLUGS = set()
    with open(SLUG_FILE, encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if r["slug"]:
                SLUGS.add(r["slug"].strip().lower())


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    return (u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()) or None


def role_slugs(company):
    s = set()
    uid = company.get("lnkd_uid")
    if uid:
        s.add(str(uid).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        sl = slug_from_url(company.get(k))
        if sl:
            s.add(sl)
    return s


def _stem(path):
    return os.path.basename(os.path.dirname(path)) + "__" + os.path.basename(path).replace(".jsonl.gz", "").replace(".jsonl", "")


def scan_file(path):
    stem = _stem(path)
    out_tmp = os.path.join(SHARD_DIR, stem + ".csv.gz.tmp"); out_fin = os.path.join(SHARD_DIR, stem + ".csv.gz")
    side_tmp = os.path.join(SIDE_DIR, stem + ".side.gz.tmp"); side_fin = os.path.join(SIDE_DIR, stem + ".side.gz")
    cols = OUTPUT_COLUMNS[:-1]
    n = 0
    gz = gzip.open(out_tmp, "wt", encoding="utf-8", newline="")
    w = csv.DictWriter(gz, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
    w.writeheader()
    sgz = gzip.open(side_tmp, "wt", encoding="utf-8", newline="")
    sw = csv.writer(sgz, quoting=csv.QUOTE_ALL); sw.writerow(["uid", "matched_slugs"])
    with gzip.open(path, "rb") as f:
        for line in f:
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            hits = set()
            for e in d.get("experience") or []:
                comp = e.get("company") or {}
                hits |= (role_slugs(comp) & SLUGS)
            if hits:
                row = row_for(d, None); row.pop("matched_company_slug", None)
                w.writerow(row)
                sw.writerow([d.get("uid"), "|".join(sorted(hits))])
                n += 1
    gz.close(); sgz.close()
    os.replace(out_tmp, out_fin); os.replace(side_tmp, side_fin)
    return stem, n


def tasks():
    out = []
    for p in POOLS:
        out += glob.glob(os.path.join(p, "*.jsonl.gz"))
    out.sort(key=os.path.getsize, reverse=True)
    return out[:LIMIT] if LIMIT else out


def main():
    os.makedirs(SHARD_DIR, exist_ok=True); os.makedirs(SIDE_DIR, exist_ok=True)
    init()
    print(f"slugs: {len(SLUGS):,} | pools {[os.path.basename(p) for p in POOLS]}", flush=True)
    shards = tasks()
    todo = [s for s in shards if not os.path.exists(os.path.join(SHARD_DIR, _stem(s) + ".csv.gz"))]
    print(f"shards {len(shards)} | done {len(shards)-len(todo)} | to scan {len(todo)} | workers {WORKERS}", flush=True)
    total = 0; t0 = time.time()
    if todo:
        with Pool(WORKERS, initializer=init) as pool:
            for i, (stem, n) in enumerate(pool.imap_unordered(scan_file, todo), 1):
                total += n
                if i % 20 == 0 or i == len(todo):
                    print(f"  scanned {i}/{len(todo)}  new matches {total:,}  ({time.time()-t0:,.0f}s)", flush=True)
    # true total from sidecars (no embedded newlines)
    grand = 0
    for s in shards:
        sp = os.path.join(SIDE_DIR, _stem(s) + ".side.gz")
        if os.path.exists(sp):
            with gzip.open(sp, "rt", encoding="utf-8", newline="") as f:
                grand += max(0, sum(1 for _ in f) - 1)
    print(f"\n==== PULL DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  total matched profiles (all shards): {grand:,}")
    print(f"  shards -> {SHARD_DIR}")


if __name__ == "__main__":
    main()
