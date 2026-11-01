# Purpose: Pull every profile CURRENTLY working (Jani's logic: a role at the 'microsoft' page with
#   duration.present OR a start date and no end date) into ONE new CSV, all ORIGINAL columns, nothing added.
#   Source = the Track-1 pulled shards (already all original columns). Workers write per-shard partials to a
#   temp dir outside the data; main merges them with a single header and deletes partials. Read-only on source.
import ast, csv, glob, gzip, json, os, shutil, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"
OUT_CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Microsoft_current_41k.csv"
TMP_DIR = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\ms_partials"
WORKERS = 15
TARGET = {"microsoft"}


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


def is_ms_current(exp):
    for e in exp if isinstance(exp, list) else []:
        if not isinstance(e, dict):
            continue
        if role_slugs(e.get("company") or {}) & TARGET:
            dur = e.get("duration") or {}
            if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                return True
    return False


def worker(path):
    base = os.path.basename(path).replace(".csv.gz", "")
    out = os.path.join(TMP_DIR, base + ".part.csv")
    n = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        w = None
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
            if is_ms_current(exp):
                w.writerow(row); n += 1
        fh.close()
    return out, cols, n


def main():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR, exist_ok=True)
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"shards {len(shards)} | workers {WORKERS}", flush=True)
    parts = []; cols = None; total = 0
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for out, c, n in pool.imap_unordered(worker, shards):
            parts.append(out); cols = c or cols; total += n
    # merge
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols)
        for p in parts:
            if os.path.getsize(p) == 0:
                continue
            with open(p, "r", encoding="utf-8", newline="") as fi:
                for line in fi:
                    fo.write(line)
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    sz = os.path.getsize(OUT_CSV) / 1e6
    print(f"\n==== MICROSOFT current pull done ({time.time()-t0:,.0f}s) ====")
    print(f"  rows written : {total:,}")
    print(f"  columns      : {len(cols)} (all original, none added)")
    print(f"  file         : {OUT_CSV}  ({sz:,.0f} MB)")


if __name__ == "__main__":
    main()
