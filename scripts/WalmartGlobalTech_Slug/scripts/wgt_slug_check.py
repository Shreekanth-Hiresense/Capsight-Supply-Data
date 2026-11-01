# Purpose: In the 9M supply (48 gzip shards), find profiles whose experience is at the exact LinkedIn
#   company entities walmartglobaltech / walmartglobaltechindia (matched by company SLUG via lnkd_uid or
#   the /company/<slug> segment of lnkd_url1/url2 - not by display name). Report: is the company present,
#   how many distinct profiles, and how many are CURRENTLY working there (a role with duration.present)
#   vs worked there in the past only. Read-only; parallel 15-worker scan.
import ast, csv, glob, gzip, os, time
from collections import defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"  # not used; shards are below
SHARDS = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\GCC_9M_shards"
TARGETS = {"walmartglobaltech", "walmartglobaltechindia"}
WORKERS = 15


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    seg = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
    return seg or None


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


def worker(path):
    # per slug: uid -> present_any (True if any current/duration.present role at that slug)
    res = {t: {} for t in TARGETS}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            cell = row.get("experience") or ""
            if "walmartglobaltech" not in cell.lower():   # cheap prefilter
                continue
            try:
                exp = ast.literal_eval(cell)
            except Exception:
                continue
            if not isinstance(exp, list):
                continue
            uid = row.get("uid")
            for e in exp:
                if not isinstance(e, dict):
                    continue
                comp = e.get("company") or {}
                hit = role_slugs(comp) & TARGETS
                if not hit:
                    continue
                present = bool((e.get("duration") or {}).get("present"))
                for t in hit:
                    if uid not in res[t] or present:
                        res[t][uid] = res[t].get(uid, False) or present
    return res


def main():
    shards = sorted(glob.glob(os.path.join(SHARDS, "*.csv.gz")))
    print(f"scanning {len(shards)} shards, {WORKERS} workers, slugs={sorted(TARGETS)}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, shards), 1):
            for t, d in res.items():
                for uid, pres in d.items():
                    merged[t][uid] = merged[t].get(uid, False) or pres
            if i % 10 == 0:
                print(f"  {i}/{len(shards)} ({time.time()-t0:,.0f}s)", flush=True)

    print(f"\n==== WALMART GLOBAL TECH slug check  ({time.time()-t0:,.0f}s) ====")
    all_uids = set()
    all_current = set()
    for t in sorted(TARGETS):
        d = merged[t]
        total = len(d)
        current = sum(1 for v in d.values() if v)
        past = total - current
        all_uids |= set(d.keys())
        all_current |= {u for u, v in d.items() if v}
        status = "PRESENT" if total else "NOT FOUND"
        print(f"\n  {t}:  {status}")
        print(f"    distinct profiles        : {total:,}")
        print(f"    currently working here   : {current:,}")
        print(f"    worked here in the past  : {past:,}")
    print(f"\n  COMBINED (either slug, distinct people):")
    print(f"    distinct profiles        : {len(all_uids):,}")
    print(f"    currently working        : {len(all_current):,}")
    print(f"    past only                : {len(all_uids) - len(all_current):,}")


if __name__ == "__main__":
    main()
