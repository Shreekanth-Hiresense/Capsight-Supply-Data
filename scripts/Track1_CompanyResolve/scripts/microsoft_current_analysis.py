# Purpose: Explain the Microsoft "currently working" count. Over the Track-1 pulled shards, for profiles
#   with a CURRENT role at the 'microsoft' page, break down by how fresh that role is: whether it has a
#   start date at all, and the start-year distribution (ref month 2026-08). A role marked present but
#   started long ago and never closed is the "staleness" that inflates a snapshot count vs a live tool
#   like Sales Navigator. Also reports how many have Microsoft as their SINGLE current employer vs one of
#   several concurrent current roles. Read-only.
import ast, csv, glob, gzip, json, os, time
from collections import Counter
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"
WORKERS = 15
TARGET = {"microsoft"}
REF_Y = 2026


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    return (u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()) or None


def role_slugs(c):
    s = set()
    if c.get("lnkd_uid"):
        s.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        sl = slug_from_url(c.get(k))
        if sl:
            s.add(sl)
    return s


def yr(start):
    try:
        return int(str(start)[:4])
    except Exception:
        return None


def worker(path):
    c = Counter()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            if not isinstance(exp, list):
                continue
            ms_present = []     # start years of present microsoft roles
            ms_present_nostart = 0
            n_other_current = 0
            has_ms_present = False
            for e in exp:
                if not isinstance(e, dict):
                    continue
                dur = e.get("duration") or {}
                present = bool(dur.get("present"))
                is_ms = bool(role_slugs(e.get("company") or {}) & TARGET)
                if is_ms and present:
                    has_ms_present = True
                    y = yr(dur.get("start"))
                    if y:
                        ms_present.append(y)
                    else:
                        ms_present_nostart += 1
                elif present and not is_ms:
                    n_other_current += 1
            if not has_ms_present:
                continue
            c["total_current_ms"] += 1
            # freshness by most-recent present-ms start
            years = ms_present
            if not years and ms_present_nostart:
                c["no_start_date"] += 1
            elif years:
                y = max(years)
                age = REF_Y - y
                if age <= 2:
                    c["start_0_2y"] += 1
                elif age <= 5:
                    c["start_3_5y"] += 1
                elif age <= 10:
                    c["start_6_10y"] += 1
                elif age <= 15:
                    c["start_11_15y"] += 1
                else:
                    c["start_15y_plus"] += 1
            if n_other_current > 0:
                c["also_has_other_current"] += 1
    return c


def main():
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"shards {len(shards)} | workers {WORKERS}", flush=True)
    C = Counter()
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for c in pool.imap_unordered(worker, shards):
            C.update(c)
    tot = C["total_current_ms"]
    print(f"\n==== MICROSOFT 'currently working' (slug microsoft)  ({time.time()-t0:,.0f}s) ====")
    print(f"  total currently-working (present flag)      : {tot:,}")
    dated = tot - C['no_start_date']
    print(f"  of them, role has NO start date             : {C['no_start_date']:,} ({100*C['no_start_date']/tot:.1f}%)")
    print(f"  current-role start age (of those dated, {dated:,}):")
    for k, lab in [("start_0_2y", "0-2 yrs ago (fresh)"), ("start_3_5y", "3-5 yrs"),
                   ("start_6_10y", "6-10 yrs"), ("start_11_15y", "11-15 yrs"), ("start_15y_plus", "15+ yrs (very stale)")]:
        v = C[k]
        print(f"     {lab:24s}: {v:>8,} ({100*v/tot:.1f}%)")
    print(f"  also hold another current (non-MS) role     : {C['also_has_other_current']:,} ({100*C['also_has_other_current']/tot:.1f}%)")


if __name__ == "__main__":
    main()
