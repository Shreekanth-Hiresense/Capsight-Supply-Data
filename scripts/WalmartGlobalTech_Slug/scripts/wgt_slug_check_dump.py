# Purpose: Same Walmart Global Tech slug check, but over the WHOLE passive_IN dump (both ziplabs_passive_IN_*
#   folders, ~97.6M profiles) instead of the 9M shards. Match experience company by SLUG (lnkd_uid or the
#   /company/<slug> segment of lnkd_url1/url2) for walmartglobaltech / walmartglobaltechindia; report
#   present?, distinct profiles, currently-working (duration.present) vs past. Read-only; 15-worker scan.
import glob, gzip, os, time
from collections import defaultdict
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
TARGETS = {"walmartglobaltech", "walmartglobaltechindia"}
WORKERS = 15
assert "hiresense_data_ziplabs" in ZIP_ROOT  # source is read-only; we only read


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
    res = {t: {} for t in TARGETS}
    with gzip.open(path, "rb") as f:
        for line in f:
            if b"walmartglobaltech" not in line.lower():   # cheap raw-bytes prefilter
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            for e in d.get("experience") or []:
                if not isinstance(e, dict):
                    continue
                comp = e.get("company") or {}
                hit = role_slugs(comp) & TARGETS
                if not hit:
                    continue
                present = bool((e.get("duration") or {}).get("present"))
                for t in hit:
                    res[t][uid] = res[t].get(uid, False) or present
    return res


def tasks():
    out = []
    for p in POOLS:
        out += glob.glob(os.path.join(p, "*.jsonl.gz"))
    out.sort(key=os.path.getsize, reverse=True)
    return out


def main():
    shards = tasks()
    print(f"dump pools: {[os.path.basename(p) for p in POOLS]}  shards: {len(shards)}  workers: {WORKERS}", flush=True)
    merged = {t: {} for t in TARGETS}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(worker, shards), 1):
            for t, d in res.items():
                for uid, pres in d.items():
                    merged[t][uid] = merged[t].get(uid, False) or pres
            if i % 25 == 0:
                print(f"  {i}/{len(shards)} ({time.time()-t0:,.0f}s)", flush=True)

    print(f"\n==== WALMART GLOBAL TECH slug check — WHOLE passive_IN DUMP  ({time.time()-t0:,.0f}s) ====")
    all_uids, all_current = set(), set()
    for t in sorted(TARGETS):
        d = merged[t]
        total = len(d); current = sum(1 for v in d.values() if v)
        all_uids |= set(d); all_current |= {u for u, v in d.items() if v}
        print(f"\n  {t}:  {'PRESENT' if total else 'NOT FOUND'}")
        print(f"    distinct profiles        : {total:,}")
        print(f"    currently working here   : {current:,}")
        print(f"    worked here in the past  : {total-current:,}")
    print(f"\n  COMBINED (either slug, distinct people):")
    print(f"    distinct profiles        : {len(all_uids):,}")
    print(f"    currently working        : {len(all_current):,}")
    print(f"    past only                : {len(all_uids)-len(all_current):,}")


if __name__ == "__main__":
    main()
