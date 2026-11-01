# Purpose: APPLY the location normalization to the actual profile data. Using the per-profile result
#   (Company_Location_Normalized_profiles.csv), write the final location-tagged profile files: 32 ORIGINAL
#   columns + company + final_location + confidence (the requested normalization tags), one row per
#   (profile x company), EXCLUDED profiles dropped. One output CSV per track. Reconciles written vs mapping.
#   Reads the track shards to get the 32 columns (read-only on shards). Disk-checked.
import csv, glob, gzip, os, sys, time
from collections import defaultdict, Counter
from multiprocessing import Pool

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from disk_guard import check_disk, warn_after_write

csv.field_size_limit(2 ** 31 - 1)
MAP = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Location_Normalized_profiles.csv"
SHARDS = {
    "track1": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn",
    "track2": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn",
    "part2":  r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\shards",
}
OUT = {
    "track1": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_location_tagged.csv",
    "track2": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_location_tagged.csv",
    "part2":  r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_location_tagged.csv",
}
TAGS = None  # (track,uid) -> list of (company, final_location, confidence)


def load_map():
    # one location per profile (uid): prefer a High-confidence assignment, else the first.
    best = {}                       # (track,uid) -> (rank, final_location)
    tagged = defaultdict(set); excl_only = defaultdict(set)
    for r in csv.DictReader(open(MAP, encoding="utf-8")):
        key = (r["track"], r["uid"])
        if r["status"] == "excluded":
            excl_only[r["track"]].add(r["uid"]); continue
        tagged[r["track"]].add(r["uid"])
        rank = 2 if r["confidence"] == "High" else 1
        if key not in best or rank > best[key][0]:
            best[key] = (rank, r["final_location"])
    m = {k: v[1] for k, v in best.items()}
    exc = Counter({t: len(s - tagged[t]) for t, s in excl_only.items()})   # uids excluded everywhere
    return m, exc


def worker(args):
    tk, path = args
    rows = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        for row in rd:
            loc = TAGS.get((tk, row.get("uid")))
            if loc is None:
                continue
            rows.append([row.get(c, "") for c in cols] + [loc])
    return tk, cols, rows


def init(m):
    global TAGS
    TAGS = m


def main():
    t0 = time.time()
    m, exc = load_map()
    kept = len(m)
    print(f"mapping: {kept:,} tagged profiles (one row per uid) | excluded-everywhere per track {dict(exc)}", flush=True)
    check_disk(kept * 2500 / 1e9, label="location-tagged profile files")
    tasks = []
    for tk, d in SHARDS.items():
        for p in sorted(glob.glob(os.path.join(d, "*.csv.gz"))):
            tasks.append((tk, p))
    writers = {}; files = {}; cols_by = {}; written = Counter()
    with Pool(10, initializer=init, initargs=(m,)) as pool:
        for tk, cols, rows in pool.imap_unordered(worker, tasks):
            if tk not in writers:
                files[tk] = open(OUT[tk], "w", encoding="utf-8", newline="")
                writers[tk] = csv.writer(files[tk], quoting=csv.QUOTE_ALL)
                writers[tk].writerow(cols + ["final_location"])
                cols_by[tk] = cols
            for row in rows:
                writers[tk].writerow(row); written[tk] += 1
    for fh in files.values():
        fh.close()
    print(f"\n==== location tags applied ({time.time()-t0:,.0f}s) ====")
    for tk in SHARDS:
        print(f"  {tk:8s} tagged profiles written {written[tk]:>9,} | excluded (dropped) {exc.get(tk,0):>8,} "
              f"-> {OUT[tk]}")
        warn_after_write(OUT[tk])
    print(f"  TOTAL tagged profiles written {sum(written.values()):,} (should equal mapping {kept:,})")


if __name__ == "__main__":
    main()
