# Purpose: Export the CURRENTLY-WORKING (Jani) profiles for Samsung, Ericsson, Nokia (Track-2) into ONE CSV,
#   all 32 ORIGINAL columns, no added columns. Reads the live Track-2 >=20 extracted set (shards_min20conn)
#   and the current (capped) final_slugs. A person currently working (present OR start-no-end) at any of the
#   three companies' slugs is included once (dedup by uid). Workers write per-shard partials, main merges.
import ast, csv, glob, gzip, json, os, shutil, time
from collections import Counter
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
FINAL = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv"
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\test_samsung,ericsson,nokia.csv"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\sen_parts"
WORKERS = 12
COMPANIES = {"samsung", "ericsson", "nokia"}
SLUGS = None


def init():
    global SLUGS
    SLUGS = {}
    for r in csv.DictReader(open(FINAL, encoding="utf-8")):
        if (r.get("company_target") or "").strip().lower() in COMPANIES and r.get("slug"):
            SLUGS[r["slug"].strip().lower()] = r["company_target"].strip().lower()


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
    base = os.path.basename(path)
    out = os.path.join(TMP, base + ".csv")
    per = Counter()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        fh = open(out, "w", encoding="utf-8", newline="")
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        for row in rd:
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            comps_cur = set()
            for e in exp if isinstance(exp, list) else []:
                if not isinstance(e, dict):
                    continue
                hit = role_slugs(e.get("company") or {}) & SLUGS.keys()
                if not hit:
                    continue
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    for s in hit:
                        comps_cur.add(SLUGS[s])
            if comps_cur:
                w.writerow(row)
                for c in comps_cur:
                    per[c] += 1
        fh.close()
    return out, cols, per


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    init()
    print(f"slugs: {len(SLUGS)} across {COMPANIES}", flush=True)
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    parts = []; cols = None; PER = Counter(); t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for out, c, per in pool.imap_unordered(worker, shards):
            parts.append(out); cols = cols or c; PER.update(per)
    total = 0
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols)
        for p in sorted(parts):
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for line in fi:
                    fo.write(line); total += 1
    total -= 0  # header not counted (partials have no header)
    shutil.rmtree(TMP, ignore_errors=True)
    sz = os.path.getsize(OUT) / 1e6
    print(f"\n==== DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  currently-working rows written (distinct profiles): {total:,}")
    print(f"  per-company (a profile at >1 counts in each): {dict(PER)}")
    print(f"  columns: {len(cols)} (all original, none added)")
    print(f"  -> {OUT}  ({sz:,.0f} MB)")


if __name__ == "__main__":
    main()
