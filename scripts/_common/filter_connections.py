# Purpose: Remove profiles with fewer than MIN connections from an exported track's shards (TRACK env),
#   writing FILTERED copies to a NEW folder (original pulled shards are frozen, never overwritten). Keeps
#   all original columns, nothing added. A blank/unparseable connections value = UNKNOWN -> KEPT (not
#   removed on a technicality) and counted separately. Reports total / removed(<MIN) / blank-kept / kept.
#   Usage: TRACK=track1 python filter_connections.py   (MIN defaults to 10)
import csv, glob, gzip, os, sys, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
MIN = int(os.environ.get("MIN", "10"))
CFG = {
    "track1": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles",
    "track2": r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles",
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1 or track2")
SRC = os.path.join(CFG[TRACK], os.environ.get("SRC_SUB", "shards"))
DST = os.path.join(CFG[TRACK], f"shards_min{MIN}conn")
WORKERS = 15


def worker(path):
    base = os.path.basename(path)
    out_tmp = os.path.join(DST, base + ".tmp"); out_fin = os.path.join(DST, base)
    total = removed = blank = kept = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        gz = gzip.open(out_tmp, "wt", encoding="utf-8", newline="")
        w = csv.DictWriter(gz, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rd:
            total += 1
            raw = (row.get("miniprofile_connections") or "").strip()
            try:
                c = int(float(raw))
            except Exception:
                c = None
            if c is None:
                blank += 1          # blank/unknown -> REMOVED (per user)
            elif c < MIN:
                removed += 1
            else:
                w.writerow(row); kept += 1
        gz.close()
    os.replace(out_tmp, out_fin)
    return total, removed, blank, kept


def main():
    os.makedirs(DST, exist_ok=True)
    shards = sorted(glob.glob(os.path.join(SRC, "*.csv.gz")))
    print(f"[{TRACK}] MIN={MIN} | shards {len(shards)} | src {SRC}", flush=True)
    T = R = B = K = 0
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for total, removed, blank, kept in pool.imap_unordered(worker, shards):
            T += total; R += removed; B += blank; K += kept
    print(f"\n==== {TRACK.upper()} connections>={MIN} filter ({time.time()-t0:,.0f}s) ====")
    print(f"  total profiles            : {T:,}")
    print(f"  removed (<{MIN} connections): {R:,} ({100*R/T:.1f}%)")
    print(f"  removed (blank/unknown)    : {B:,} ({100*B/T:.1f}%)")
    print(f"  kept (>= {MIN}, numeric)     : {K:,} ({100*K/T:.1f}%)")
    print(f"  filtered shards -> {DST}")


if __name__ == "__main__":
    main()
