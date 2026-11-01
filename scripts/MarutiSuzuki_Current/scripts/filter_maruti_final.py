# Purpose: FINAL Maruti Suzuki deliverable. Keep only currently-working (Jani) profiles that are (a) in the 3
#   areas AND (b) classified into one of the user's 11 functions (via the taxonomy cache + report_11 mapping).
#   Filter MarutiSuzuki_current_3areas.csv down to those uids, write MarutiSuzuki_final_11functions.csv (32
#   original columns, QUOTE_ALL, no added columns). Report per-area and per-function counts.
import csv, sys
from collections import Counter

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\MarutiSuzuki_Current\scripts")
from report_11_functions import bucket, ORDER

csv.field_size_limit(2 ** 31 - 1)
SRC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_current_3areas.csv"
CACHE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_taxonomy_cache.csv"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_final_11functions.csv"

keep = {}   # uid -> (area, function)
with open(CACHE, encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        b = bucket(r["L1"], r["L2"], r["L3_Role"])
        if b:
            keep[r["uid"]] = (r["area"], b)

per_area = Counter(); per_fn = Counter(); area_fn = Counter()
written = 0
with open(SRC, encoding="utf-8", newline="") as fi, open(OUT, "w", encoding="utf-8", newline="") as fo:
    rd = csv.reader(fi); w = csv.writer(fo, quoting=csv.QUOTE_ALL)
    hdr = next(rd); w.writerow(hdr)
    ui = hdr.index("uid")
    for row in rd:
        uid = row[ui]
        if uid in keep:
            w.writerow(row); written += 1
            area, fn = keep[uid]
            per_area[area] += 1; per_fn[fn] += 1; area_fn[(area, fn)] += 1

print(f"KEPT (in-11, 3 areas): {written:,}  -> {OUT}")
print("\n--- by area ---")
for a, c in per_area.most_common():
    print(f"  {a:26s} {c:>6,}")
print("\n--- by function (all 3 areas) ---")
for fn in ORDER:
    print(f"  {fn:38s} {per_fn.get(fn,0):>6,}")
print(f"  {'TOTAL':38s} {written:>6,}")
