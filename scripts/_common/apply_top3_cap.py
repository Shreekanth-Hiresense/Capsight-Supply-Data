# Purpose: Enforce "max 3 entity pages per company" on a track's final_slugs (TRACK env). Rank each company's
#   slugs by TRUE unique-profile count (from the pulled sidecars) and KEEP only the top 3; drop the rest from
#   final_slugs (backed up to final_slugs_precap_<ts>.csv). EXCEPTION companies (explicit per-company rules)
#   are left exactly as-is. Physical profile removal happens afterwards via finalize_extracted (profiles
#   unique to a dropped page stop qualifying and get removed; multi-page/multi-company people are kept).
#   Usage: TRACK=track1|track2|part2 python apply_top3_cap.py
import csv, glob, gzip, os, re, sys, time, unicodedata
from collections import Counter, defaultdict

csv.field_size_limit(2 ** 31 - 1)
TRACK = os.environ.get("TRACK", "").lower()
CFG = {
    "track1": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv",
                   col="company", side=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\_sidecars"),
    "track2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv",
                   col="company_target", side=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\_sidecars"),
    "part2": dict(final=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv",
                  col="company_target", side=r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_Part2_profiles\_sidecars"),
}
if TRACK not in CFG:
    sys.exit("set TRACK=track1|track2|part2")
C = CFG[TRACK]

# exception companies: keep their slugs exactly as set (no cap)
EXC_EXACT = {"ey"}
EXC_SUB = ["kpmg", "pwc", "ernst", "deloitte", "goldman sachs", "amazon", "d e shaw", "pepsico",
           "mercedes", "bosch", "teleperformance", "siemens", "philips", "ntt data"]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s) or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def is_exception(label):
    n = norm(label)
    return n in EXC_EXACT or any(sub in n for sub in EXC_SUB)


def slug_counts():
    cnt = Counter()
    for sp in glob.glob(os.path.join(C["side"], "*.side.gz")):
        with gzip.open(sp, "rt", encoding="utf-8", newline="") as f:
            rd = csv.reader(f); next(rd, None)
            for row in rd:
                if len(row) < 2:
                    continue
                for sl in row[1].split("|"):
                    sl = sl.strip().lower()
                    if sl:
                        cnt[sl] += 1
    return cnt


def main():
    rows = list(csv.DictReader(open(C["final"], encoding="utf-8")))
    cols = list(rows[0].keys())
    by = defaultdict(list)
    for r in rows:
        by[r[C["col"]]].append(r)
    cnt = slug_counts()
    kept_rows = []; capped = 0; removed_slugs = 0; exc = 0
    for comp, rs in by.items():
        if is_exception(comp):
            kept_rows.extend(rs); exc += 1
            continue
        if len(rs) <= 3:
            kept_rows.extend(rs)
            continue
        rs_sorted = sorted(rs, key=lambda r: -cnt.get(r["slug"].strip().lower(), 0))
        kept_rows.extend(rs_sorted[:3])
        capped += 1; removed_slugs += len(rs) - 3
    bak = C["final"].replace(".csv", f"_precap_{int(time.time())}.csv")
    os.replace(C["final"], bak)
    with open(C["final"], "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(kept_rows)
    print(f"[{TRACK}] companies {len(by)} | exceptions kept-as-is {exc} | capped to top3 {capped} | "
          f"slugs removed {removed_slugs} | final_slugs now {len(kept_rows)} rows (backup {os.path.basename(bak)})")


if __name__ == "__main__":
    main()
