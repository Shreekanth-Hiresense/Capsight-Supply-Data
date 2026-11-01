# Purpose: Create the Bosch file with ONLY the two kept entities: bosch-global-software-technologies (BGSW)
#   and bosch-india. Pull from the 97M dump (read-only), keep connections>=10, write all 32 original columns
#   to one CSV. Report per-slug + combined DISTINCT ever / current-normal / current-Jani (before & after >=10).
import csv, glob, gzip, os, sys, time
from multiprocessing import Pool
import orjson
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS  # noqa: E402

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Bosch_BGSW_India_conn10.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\bosch_parts"
WORKERS = 12
SLUGS = {"bosch-global-software-technologies", "bosch-india"}
PRE = b"bosch"
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
    st = {k: set() for k in ("bgsw_e", "bgsw_n", "bgsw_j", "ind_e", "ind_n", "ind_j",
                             "any_e", "any_n", "any_j", "bgsw_e10", "bgsw_n10", "bgsw_j10",
                             "ind_e10", "ind_n10", "ind_j10", "any_e10", "any_n10", "any_j10")}
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
            bg = ind = bgn = indn = bgj = indj = False
            for e in d.get("experience") or []:
                hit = role_slugs(e.get("company") or {}) & SLUGS
                if not hit:
                    continue
                dur = e.get("duration") or {}
                present = bool(dur.get("present")); cj = present or ((not dur.get("end")) and dur.get("start"))
                if "bosch-global-software-technologies" in hit:
                    bg = True; bgn |= present; bgj |= bool(cj)
                if "bosch-india" in hit:
                    ind = True; indn |= present; indj |= bool(cj)
            if not (bg or ind):
                continue
            try:
                c10 = int((d.get("miniprofile") or {}).get("connections")) >= 10
            except Exception:
                c10 = False
            if bg:
                st["bgsw_e"].add(uid); bgn and st["bgsw_n"].add(uid); bgj and st["bgsw_j"].add(uid)
            if ind:
                st["ind_e"].add(uid); indn and st["ind_n"].add(uid); indj and st["ind_j"].add(uid)
            st["any_e"].add(uid); (bgn or indn) and st["any_n"].add(uid); (bgj or indj) and st["any_j"].add(uid)
            if c10:
                if bg:
                    st["bgsw_e10"].add(uid); bgn and st["bgsw_n10"].add(uid); bgj and st["bgsw_j10"].add(uid)
                if ind:
                    st["ind_e10"].add(uid); indn and st["ind_n10"].add(uid); indj and st["ind_j10"].add(uid)
                st["any_e10"].add(uid); (bgn or indn) and st["any_n10"].add(uid); (bgj or indj) and st["any_j10"].add(uid)
                row = row_for(d, None); row.pop("matched_company_slug", None)
                w.writerow(row)
    fh.close()
    return st, out


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
        for st, out in pool.imap_unordered(worker, shards):
            parts.append(out)
            if agg is None:
                agg = {k: set() for k in st}
            for k, v in st.items():
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
    print(f"\n==== BOSCH (BGSW + bosch-india) pull ({time.time()-t0:,.0f}s) ====")
    print("FULL (all connections):")
    print(f"  bosch-global-software-technologies  ever {L['bgsw_e']:,} | cur-normal {L['bgsw_n']:,} | cur-jani {L['bgsw_j']:,}")
    print(f"  bosch-india                         ever {L['ind_e']:,} | cur-normal {L['ind_n']:,} | cur-jani {L['ind_j']:,}")
    print(f"  COMBINED distinct                   ever {L['any_e']:,} | cur-normal {L['any_n']:,} | cur-jani {L['any_j']:,}")
    print("AFTER connections>=10 (written to CSV):")
    print(f"  bosch-global-software-technologies  ever {L['bgsw_e10']:,} | cur-normal {L['bgsw_n10']:,} | cur-jani {L['bgsw_j10']:,}")
    print(f"  bosch-india                         ever {L['ind_e10']:,} | cur-normal {L['ind_n10']:,} | cur-jani {L['ind_j10']:,}")
    print(f"  COMBINED distinct                   ever {L['any_e10']:,} | cur-normal {L['any_n10']:,} | cur-jani {L['any_j10']:,}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
