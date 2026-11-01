# Purpose: Same current-working variants as slug_current_variants.py, but over a folder of CSV.GZ shards
#   (e.g. the 4.2M Track-1 pulled set), reading the 'experience' column (Python-repr, parsed with
#   ast.literal_eval; json fallback). Reports, per distinct profile at a target slug:
#     NORMAL = duration.present only
#     V1     = present + role with neither start nor end given
#     V2     = present + role with a start date but no end date   (<- user's logic v2)
#     BROAD  = present + any role with no end date
#   Usage: SHARDS="...\Track1_BySlug_profiles\shards" SLUGS="citi,hsbc" python slug_current_variants_shards.py
import ast, csv, glob, gzip, json, os, sys, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = os.environ.get("SHARDS", r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards")
TARGETS = tuple(s.strip().lower() for s in os.environ.get("SLUGS", "").split(",") if s.strip())
WORKERS = 15
if not TARGETS:
    sys.exit("set SLUGS env")


def slug_from_url(u):
    if not u:
        return None
    for marker in ("/company/", "/showcase/"):
        if marker in u:
            return (u.rstrip("/").split(marker)[-1].split("/")[0].strip().lower()) or None
    return None


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


def classify(dur):
    present = bool(dur.get("present"))
    end = dur.get("end")
    start = dur.get("start")
    if present:
        return "present"
    if end:
        return "ended"
    return "no_start_no_end" if not start else "start_no_end"


def parse_exp(cell):
    if not cell:
        return []
    try:
        v = ast.literal_eval(cell)
    except Exception:
        try:
            v = json.loads(cell)
        except Exception:
            return []
    return v if isinstance(v, list) else []


def worker(path):
    res = {t: {} for t in TARGETS}
    tset = set(TARGETS)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cell = row.get("experience") or ""
            low = cell.lower()
            if not any(t in low for t in TARGETS):
                continue
            uid = row.get("uid")
            for e in parse_exp(cell):
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & tset
                if not hit:
                    continue
                cls = classify(e.get("duration") or {})
                for t in hit:
                    res[t].setdefault(uid, set()).add(cls)
    return res


def main():
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"slugs={list(TARGETS)}  shards={len(shards)} in {SHARD_DIR}  workers={WORKERS}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for res in pool.imap_unordered(worker, shards):
            for t, d in res.items():
                for uid, classes in d.items():
                    merged[t].setdefault(uid, set()).update(classes)
    print(f"\n==== CURRENT-WORKING VARIANTS (4.2M Track-1 set)  ({time.time()-t0:,.0f}s) ====")
    for t in TARGETS:
        d = merged[t]
        ever = len(d)
        strict = sum(1 for c in d.values() if "present" in c)
        v1 = sum(1 for c in d.values() if ("present" in c) or ("no_start_no_end" in c))
        v2 = sum(1 for c in d.values() if ("present" in c) or ("start_no_end" in c))
        broad = sum(1 for c in d.values() if c & {"present", "no_start_no_end", "start_no_end"})
        print(f"\n  {t}:  ever worked (distinct) = {ever:,}")
        print(f"    NORMAL current  (duration.present only)                   : {strict:,}")
        print(f"    V1     current  (present + neither start nor stop given)   : {v1:,}   (+{v1-strict:,})")
        print(f"    V2     current  (present + start given but no end date)    : {v2:,}   (+{v2-strict:,})")
        print(f"    BROAD  current  (present + any role with no end date)      : {broad:,}   (+{broad-strict:,})")


if __name__ == "__main__":
    main()
