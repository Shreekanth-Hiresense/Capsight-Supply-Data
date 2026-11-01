# Purpose: Generic merge of a pulled company CSV into the Track-1 EXTRACTED set (shards_min10conn), adding
#   only rows whose uid is not already present, as one new shard. CSV env = source CSV; TAG env = short name
#   for the new shard (zz_<tag>_added__conn10.csv.gz). Read-only on existing shards (adds one file).
#   Usage: CSV="...\Bosch_BGSW_India_conn10.csv" TAG=bosch python merge_csv_into_extracted.py
import csv, glob, gzip, os, sys, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min10conn"
CSVP = os.environ.get("CSV", "")
TAG = os.environ.get("TAG", "")
if not CSVP or not TAG:
    sys.exit("set CSV= and TAG=")
ADDED = os.path.join(SHARD_DIR, f"zz_{TAG}_added__conn10.csv.gz")
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
    with open(CSVP, "r", encoding="utf-8", newline="") as fi:
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
    print(f"\n==== merge {TAG} into extracted set ====")
    print(f"  source rows               : {total:,}")
    print(f"  already in extracted set  : {dup:,}")
    print(f"  NEWLY ADDED               : {added:,}")
    print(f"  new shard -> {ADDED}")


if __name__ == "__main__":
    main()
