# Purpose: Fold the D.E. Shaw profiles (both pages) into the Track-1 EXTRACTED set (shards_min10conn), so
#   both entities live in the dump, not a separate CSV. Steps: collect all uids already in shards_min10conn;
#   from DEShaw_both_conn10.csv add only the rows whose uid is NOT already there (the India-only people) as a
#   new shard 'zz_deshaw_added__conn10.csv.gz' inside shards_min10conn. Reports how many added. Read-only on
#   existing shards (adds one new file).
import csv, glob, gzip, os, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min10conn"
DESHAW_CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\DEShaw_both_conn10.csv"
ADDED = os.path.join(SHARD_DIR, "zz_deshaw_added__conn10.csv.gz")
WORKERS = 10


def uids_in(path):
    s = set()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            u = row.get("uid")
            if u:
                s.add(u)
    return s


def main():
    shards = [p for p in sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
              if os.path.basename(p) != os.path.basename(ADDED)]
    print(f"collecting uids from {len(shards)} extracted shards...", flush=True)
    t0 = time.time()
    existing = set()
    with Pool(WORKERS) as pool:
        for s in pool.imap_unordered(uids_in, shards):
            existing |= s
    print(f"  existing uids: {len(existing):,} ({time.time()-t0:,.0f}s)", flush=True)
    # add India-only D.E. Shaw rows
    with open(DESHAW_CSV, "r", encoding="utf-8", newline="") as fi:
        rd = csv.DictReader(fi); cols = rd.fieldnames
        gz = gzip.open(ADDED, "wt", encoding="utf-8", newline="")
        w = csv.DictWriter(gz, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        w.writeheader()
        total = added = dup = 0
        for row in rd:
            total += 1
            u = row.get("uid")
            if u in existing:
                dup += 1
            else:
                w.writerow(row); added += 1; existing.add(u)
        gz.close()
    print(f"\n==== D.E. SHAW merge into extracted set ====")
    print(f"  DEShaw_both_conn10 rows        : {total:,}")
    print(f"  already in extracted set       : {dup:,}")
    print(f"  NEWLY ADDED (India-only etc.)  : {added:,}")
    print(f"  new shard -> {ADDED}")


if __name__ == "__main__":
    main()
