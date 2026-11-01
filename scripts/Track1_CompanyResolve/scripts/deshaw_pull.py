# Purpose: Fully include BOTH D.E. Shaw pages by pulling them fresh from the 97M dump (read-only), then
#   keep only connections>=10. Slugs: 'd.-e.-shaw-&-co.' and 'd.-e.-shaw-india-private-limited'. Writes one
#   CSV (all 32 original columns) of the >=10-connection D.E. Shaw profiles, and reports per-slug + combined
#   DISTINCT ever / current-normal / current-Jani (before and after the >=10 filter).
import csv, glob, gzip, os, sys, time
from multiprocessing import Pool
import orjson
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS  # noqa: E402

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\DEShaw_both_conn10.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\deshaw_parts"
WORKERS = 12
SLUGS = {"d.-e.-shaw-&-co.", "d.-e.-shaw-india-private-limited"}
PRE = b"d.-e.-shaw"
assert "hiresense_data_ziplabs" not in OUT


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


def worker(path):
    base = os.path.basename(os.path.dirname(path)) + "__" + os.path.basename(path).replace(".jsonl.gz", "")
    out = os.path.join(TMP, base + ".csv")
    cols = OUTPUT_COLUMNS[:-1]
    stats = {"amp_ever": set(), "amp_n": set(), "amp_j": set(),
             "ind_ever": set(), "ind_n": set(), "ind_j": set(),
             "any_ever": set(), "any_n": set(), "any_j": set(),
             "amp_ever10": set(), "amp_n10": set(), "amp_j10": set(),
             "ind_ever10": set(), "ind_n10": set(), "ind_j10": set(),
             "any_ever10": set(), "any_n10": set(), "any_j10": set()}
    fh = open(out, "w", encoding="utf-8", newline="")
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
    with gzip.open(path, "rb") as f:
        for line in f:
            if PRE not in line.lower():
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            amp = ind = False; ampn = indn = ampj = indj = False
            for e in d.get("experience") or []:
                hit = role_slugs(e.get("company") or {}) & SLUGS
                if not hit:
                    continue
                dur = e.get("duration") or {}
                present = bool(dur.get("present")); cur_j = present or ((not dur.get("end")) and dur.get("start"))
                if "d.-e.-shaw-&-co." in hit:
                    amp = True; ampn |= present; ampj |= bool(cur_j)
                if "d.-e.-shaw-india-private-limited" in hit:
                    ind = True; indn |= present; indj |= bool(cur_j)
            if not (amp or ind):
                continue
            conn = (d.get("miniprofile") or {}).get("connections")
            try:
                c10 = int(conn) >= 10
            except Exception:
                c10 = False
            # full-set stats
            if amp:
                stats["amp_ever"].add(uid); ampn and stats["amp_n"].add(uid); ampj and stats["amp_j"].add(uid)
            if ind:
                stats["ind_ever"].add(uid); indn and stats["ind_n"].add(uid); indj and stats["ind_j"].add(uid)
            stats["any_ever"].add(uid); (ampn or indn) and stats["any_n"].add(uid); (ampj or indj) and stats["any_j"].add(uid)
            if c10:
                if amp:
                    stats["amp_ever10"].add(uid); ampn and stats["amp_n10"].add(uid); ampj and stats["amp_j10"].add(uid)
                if ind:
                    stats["ind_ever10"].add(uid); indn and stats["ind_n10"].add(uid); indj and stats["ind_j10"].add(uid)
                stats["any_ever10"].add(uid); (ampn or indn) and stats["any_n10"].add(uid); (ampj or indj) and stats["any_j10"].add(uid)
                row = row_for(d, None); row.pop("matched_company_slug", None)
                w.writerow(row)
    fh.close()
    return {k: v for k, v in stats.items()}, out


def main():
    import shutil
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"dump shards {len(shards)} | workers {WORKERS}", flush=True)
    agg = None; parts = []
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for stats, out in pool.imap_unordered(worker, shards):
            parts.append(out)
            if agg is None:
                agg = {k: set() for k in stats}
            for k, v in stats.items():
                agg[k] |= v
    cols = OUTPUT_COLUMNS[:-1]
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols)
        for p in sorted(parts):
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for line in fi:
                    fo.write(line)
    shutil.rmtree(TMP, ignore_errors=True)
    L = {k: len(v) for k, v in agg.items()}
    print(f"\n==== D.E. SHAW pull from dump ({time.time()-t0:,.0f}s) ====")
    print("FULL (all connections):")
    print(f"  d.-e.-shaw-&-co.              ever {L['amp_ever']:,} | cur-normal {L['amp_n']:,} | cur-jani {L['amp_j']:,}")
    print(f"  d.-e.-shaw-india-private-ltd  ever {L['ind_ever']:,} | cur-normal {L['ind_n']:,} | cur-jani {L['ind_j']:,}")
    print(f"  COMBINED distinct             ever {L['any_ever']:,} | cur-normal {L['any_n']:,} | cur-jani {L['any_j']:,}")
    print("\nAFTER connections>=10 (what's written to CSV):")
    print(f"  d.-e.-shaw-&-co.              ever {L['amp_ever10']:,} | cur-normal {L['amp_n10']:,} | cur-jani {L['amp_j10']:,}")
    print(f"  d.-e.-shaw-india-private-ltd  ever {L['ind_ever10']:,} | cur-normal {L['ind_n10']:,} | cur-jani {L['ind_j10']:,}")
    print(f"  COMBINED distinct             ever {L['any_ever10']:,} | cur-normal {L['any_n10']:,} | cur-jani {L['any_j10']:,}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
