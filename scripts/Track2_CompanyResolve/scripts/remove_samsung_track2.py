# Purpose: Physically remove the Track-2 SAMSUNG (company 'samsung') profiles from the Track-2 EXTRACTED set
#   (shards_min20conn), so Samsung lives only in Part-2 (user 2026-10-29). A profile is dropped only if its
#   matched Track-2 slugs (from the pull sidecars) are EXACTLY within the samsung set
#   {samsung-electronics, samsungrndindiabangalore, samsungmobile} - i.e. Samsung was its ONLY Track-2 company.
#   Anyone also at another Track-2 company (incl. 'samsung e a' = samsung-engineering-india/samsungena) is KEPT.
#   Rewrites each shard in place (tmp -> os.replace). Reports removed / remaining.
import csv, glob, gzip, os, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SIDE_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\_sidecars"
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn"
SAMSUNG = {"samsung-electronics", "samsungrndindiabangalore", "samsungmobile"}
WORKERS = 10
DROP = None


def samsung_only_uids():
    drop = set()
    for sp in glob.glob(os.path.join(SIDE_DIR, "*.side.gz")):
        with gzip.open(sp, "rt", encoding="utf-8", newline="") as f:
            rd = csv.reader(f); next(rd, None)
            for row in rd:
                if len(row) < 2:
                    continue
                slugs = {s.strip().lower() for s in row[1].split("|") if s.strip()}
                if slugs and slugs <= SAMSUNG:
                    drop.add(row[0])
    return drop


def rewrite(path):
    tmp = path + ".tmp"
    kept = removed = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        gz = gzip.open(tmp, "wt", encoding="utf-8", newline="")
        w = csv.DictWriter(gz, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rd:
            if row.get("uid") in DROP:
                removed += 1
            else:
                w.writerow(row); kept += 1
        gz.close()
    os.replace(tmp, path)
    return kept, removed


def init(drop):
    global DROP
    DROP = drop


def main():
    t0 = time.time()
    print("building samsung-only uid drop set from Track-2 sidecars...", flush=True)
    drop = samsung_only_uids()
    print(f"  samsung-only uids to drop: {len(drop):,} ({time.time()-t0:,.0f}s)", flush=True)
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    K = R = 0
    with Pool(WORKERS, initializer=init, initargs=(drop,)) as pool:
        for kept, removed in pool.imap_unordered(rewrite, shards):
            K += kept; R += removed
    print(f"\n==== Track-2 Samsung removed from extracted set ({time.time()-t0:,.0f}s) ====")
    print(f"  removed (samsung-only) : {R:,}")
    print(f"  remaining in Track-2 extracted set : {K:,}")


if __name__ == "__main__":
    main()
