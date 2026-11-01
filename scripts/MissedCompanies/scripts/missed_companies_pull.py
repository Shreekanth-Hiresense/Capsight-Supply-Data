# Purpose: Pull the MISSED (not-matched) companies using ONLY the LinkedIn URLs the user supplied in
#   Track_Company_Coverage_NotMatched.xlsx (All_NotMatched sheet: col A track, col B company, col C + col D..
#   LinkedIn URLs). No discovery, no entity-expansion. For each supplied slug: scan passive_IN (read-only),
#   keep profiles with any role at the slug, >=20 connections. Count per company: ever-worked + currently-
#   working (Jani). Track-2 Part-2 companies additionally get intern-drop + the 11-function filter on the
#   CURRENT count. Write per-track recovered profile CSVs (32 original cols, ever-worked, dedup by uid) + a
#   counts summary. No per-company special gates (none of these are Amazon/Deloitte/etc.).
import csv, glob, gzip, os, re, shutil, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
import orjson

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts")
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
import gcc_taxonomy_classifier as TC
from big_it_companies_current_employees import row_for, OUTPUT_COLUMNS
from disk_guard import check_disk, warn_after_write

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(2 ** 31 - 1)
XLSX = r"C:\Users\LENOVO\Downloads\Track_Company_Coverage_NotMatched (2).xlsx"
ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
OUTDIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\missed_parts"
WORKERS = 12
COLS = [c for c in OUTPUT_COLUMNS if c != "matched_company_slug"]
TRACKKEY = {"Track-1": "track1", "Track-2": "track2", "Track-2 Part-2": "part2"}
SLUG2 = None; PRE_RE = None; COMP = None


def load_targets():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["All_NotMatched"]
    s2 = {}
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r or not (r[0] or (len(r) > 1 and r[1])):
            continue
        raw = str(r[0]).strip() if r[0] else ""
        track = TRACKKEY.get(raw, raw) if raw else "track1"   # blank Track -> Track-1 (user: the 12 additions are T1)
        comp = str(r[1]).strip() if r[1] else ""
        for cell in r[2:]:
            if cell and "linkedin.com" in str(cell):
                m = re.search(r"/(company|showcase)/([^/?#]+)", str(cell))
                if m:
                    s2[m.group(2).strip().lower()] = (track, comp)
    return s2


def init():
    global SLUG2
    SLUG2 = load_targets()


def slugs_of(c):
    out = set()
    u = c.get("lnkd_uid")
    if u:
        out.add(str(u).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        v = c.get(k)
        if v and "/company/" in v:
            s = v.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s:
                out.add(s)
    return out


def worker(path):
    base = os.path.basename(path)
    files = {}; writers = {}
    ever = Counter(); cur = Counter()   # keyed by (track,company)
    def W(tk):
        if tk not in writers:
            fh = open(os.path.join(TMP, tk + "__" + base + ".csv"), "w", encoding="utf-8", newline="")
            files[tk] = fh; writers[tk] = csv.writer(fh, quoting=csv.QUOTE_ALL)
        return writers[tk]
    with gzip.open(path, "rb") as f:
        for line in f:
            try:
                d = orjson.loads(line)          # parse every line + set-check slugs (like pull_by_slug; no regex prefilter)
            except Exception:
                continue
            try:
                conn = int(d.get("miniprofile", {}).get("connections"))
            except Exception:
                conn = None
            if conn is None or conn < 20:
                continue
            # per matched (track,company): ever / current / titles
            comp_ever = {}; comp_cur = {}; comp_titles = defaultdict(list)
            cur_title = ""; past_titles = []; descs = []
            for e in d.get("experience") or []:
                if not isinstance(e, dict):
                    continue
                t = e.get("title") or ""
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if is_cur and not cur_title:
                    cur_title = t
                else:
                    past_titles.append(t)
                if e.get("description"):
                    descs.append(str(e.get("description")))
                hits = slugs_of(e.get("company") or {}) & SLUG2.keys()
                for s in hits:
                    key = SLUG2[s]
                    comp_ever[key] = True
                    comp_titles[key].append(t)
                    if is_cur:
                        comp_cur[key] = True
            if not comp_ever:
                continue
            tracks_hit = set()
            for key in comp_ever:
                tk, comp = key
                tracks_hit.add(tk)
                ever[key] += 1
                if comp_cur.get(key, False):
                    cur[key] += 1
            # (Part-2 11-function is computed afterward on the small recovered set, not inline here)
            # write ever-worked profile row to each matched track's partial
            r = row_for(d, None); r.pop("matched_company_slug", None)
            baserow = [r.get(c, "") for c in COLS]
            for tk in tracks_hit:
                W(tk).writerow(baserow + [d.get("uid")])
    for fh in files.values():
        fh.close()
    return ever, cur


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP, exist_ok=True)
    init()
    ntargets = len(SLUG2)
    print(f"missed slugs {ntargets} | shards (both IN pools) scanning | workers {WORKERS}", flush=True)
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    EVER = Counter(); CUR = Counter(); t0 = time.time()
    with Pool(WORKERS, initializer=init) as pool:
        for ev, cu in pool.imap_unordered(worker, shards):
            EVER.update(ev); CUR.update(cu)
    # merge per-track partials, dedup by uid -> recovered CSVs
    check_disk(2.0, label="missed recovered profiles")
    track_rows = Counter()
    for tk in ("track1", "track2", "part2"):
        out = os.path.join(OUTDIR, f"Recovered_{tk}_profiles.csv")
        seen = set()
        with open(out, "w", encoding="utf-8", newline="") as fo:
            w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(COLS)
            for p in sorted(glob.glob(os.path.join(TMP, tk + "__*.csv"))):
                with open(p, "r", encoding="utf-8", newline="") as fi:
                    for row in csv.reader(fi):
                        if not row:
                            continue
                        uid = row[-1]
                        if uid in seen:
                            continue
                        seen.add(uid); w.writerow(row[:-1]); track_rows[tk] += 1
        warn_after_write(out)
    shutil.rmtree(TMP, ignore_errors=True)
    # counts summary
    summ = os.path.join(OUTDIR, "Recovered_companies_counts.csv")
    with open(summ, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["track", "company", "ever_worked", "current_jani"])
        for (tk, comp) in sorted(EVER, key=lambda k: (k[0], -EVER[k])):
            w.writerow([tk, comp, EVER[(tk, comp)], CUR[(tk, comp)]])
    print(f"\n==== MISSED COMPANIES pulled ({time.time()-t0:,.0f}s) ====")
    for tk in ("track1", "track2", "part2"):
        tot_ever = sum(v for k, v in EVER.items() if k[0] == tk)
        tot_cur = sum(v for k, v in CUR.items() if k[0] == tk)
        print(f"  {tk:8s}: {sum(1 for k in EVER if k[0]==tk):>3} companies | ever {tot_ever:>7,} | "
              f"current(Jani) {tot_cur:>7,} | recovered rows (dedup) {track_rows[tk]:,}")
    print(f"  -> Recovered_track1/track2/part2_profiles.csv + Recovered_companies_counts.csv")


if __name__ == "__main__":
    main()
