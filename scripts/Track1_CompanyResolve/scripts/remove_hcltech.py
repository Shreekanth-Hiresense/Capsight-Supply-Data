# Purpose: Physically remove Sankalp/HCLTech profiles from the Track-1 EXTRACTED set (shards_min10conn).
#   A profile is dropped only if its matched slugs (from the pull sidecars) are EXACTLY {hcltech} - i.e. the
#   person's only Track-1 company was the (wrongly-attributed) hcltech page. Anyone who also worked at a real
#   Track-1 company is kept. Rewrites each shard in place (tmp -> os.replace). Reports removed / remaining.
import csv, glob, gzip, os, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SIDE_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\_sidecars"
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min10conn"
WORKERS = 10
DROP = None


def hcltech_only_uids():
    drop = set()
    for sp in glob.glob(os.path.join(SIDE_DIR, "*.side.gz")):
        with gzip.open(sp, "rt", encoding="utf-8", newline="") as f:
            rd = csv.reader(f); next(rd, None)
            for row in rd:
                if len(row) < 2:
                    continue
                slugs = {s.strip().lower() for s in row[1].split("|") if s.strip()}
                if slugs and slugs <= {"hcltech"}:
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
    print("building hcltech-only uid drop set from sidecars...", flush=True)
    drop = hcltech_only_uids()
    print(f"  hcltech-only uids to drop: {len(drop):,} ({time.time()-t0:,.0f}s)", flush=True)
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    K = R = 0
    with Pool(WORKERS, initializer=init, initargs=(drop,)) as pool:
        for kept, removed in pool.imap_unordered(rewrite, shards):
            K += kept; R += removed
    print(f"\n==== HCLTech/Sankalp removed from extracted set ({time.time()-t0:,.0f}s) ====")
    print(f"  removed : {R:,}")
    print(f"  remaining in extracted set : {K:,}")


if __name__ == "__main__":
    main()
