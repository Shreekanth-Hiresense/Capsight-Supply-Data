# Purpose: Curated Big-4 profile sets from the Track-1 pulled shards (one pass, read-only):
#   KPMG  = profiles with a role at slug 'kpmg-us'
#   PwC   = profiles with a role at slug 'pwc-ac-india'
#   EY    = profiles with a role at 'ernstandyoung' AND a GCC/offshore keyword anywhere in the profile
#   Deloitte = profiles with a role at any 'deloitte*' page AND a GCC/offshore keyword anywhere
#   Keyword set (acronyms word-bounded; standalone "US" EXCLUDED by default - typo in source list):
#     GDS GBS GSS GDC GCC USI KGS SSC + the long "Global ... Services/Center/Centre", "Shared Services ...",
#     "Acceleration Center/Centre", "Global Operations", "Center/Centre of Excellence".
#   Writes one CSV per company (all original columns) + reports ever / current-normal / current-Jani.
#   Also counts how many EY/Deloitte keyword-passers would be ADDED if standalone "US" were included.
import ast, csv, glob, gzip, json, os, re, shutil, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Big4_curated"
TMP = r"C:\Users\LENOVO\AppData\Local\Temp\claude\C--Shree-Shreekanth-Hiresense-JD-AI-Workflow\c84da2ee-9a61-43c4-82c4-dd7aa1dba0dd\scratchpad\big4_parts"
WORKERS = 10

KPMG = {"kpmg-us"}
PWC = {"pwc-ac-india"}
EY = {"ernstandyoung"}

ACRO = re.compile(r"\b(?:GDS|GBS|GSS|GDC|GCC|USI|KGS|SSC)\b", re.I)
PHRASE = re.compile(
    r"global delivery services|global business services|global shared services|"
    r"global capability centre|global capability center|global delivery centre|global delivery center|"
    r"shared services centre|shared services center|acceleration centre|acceleration center|"
    r"global operations|centre of excellence|center of excellence", re.I)
US_ONLY = re.compile(r"\bUS\b")   # case-sensitive US, to gauge the noisy add


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


def cur_state(exp, want):
    """return (ever, normal, jani) booleans for membership in slug set `want`"""
    ever = norm = jani = False
    for e in exp:
        if not isinstance(e, dict):
            continue
        if role_slugs(e.get("company") or {}) & want:
            ever = True
            dur = e.get("duration") or {}
            if bool(dur.get("present")):
                norm = True; jani = True
            elif (not dur.get("end")) and dur.get("start"):
                jani = True
    return ever, norm, jani


def worker(path):
    base = os.path.basename(path)
    writers = {}; files = {}
    cols_holder = {}
    counts = {k: [0, 0, 0] for k in ("kpmg", "pwc", "ey", "deloitte")}  # ever, norm, jani
    us_extra = {"ey": 0, "deloitte": 0}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f); cols = rd.fieldnames
        for cat in ("kpmg", "pwc", "ey", "deloitte"):
            fp = os.path.join(TMP, cat, base + ".csv")
            fh = open(fp, "w", encoding="utf-8", newline="")
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_ALL)
            writers[cat] = (fh, w)
        for row in rd:
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            if not isinstance(exp, list):
                exp = []
            dsl = {sl for e in exp if isinstance(e, dict) for sl in role_slugs(e.get("company") or {}) if "deloitte" in sl}
            # cheap membership checks
            def has(want):
                return any(role_slugs(e.get("company") or {}) & want for e in exp if isinstance(e, dict))
            is_k = has(KPMG); is_p = has(PWC); is_e = has(EY); is_d = bool(dsl)
            if not (is_k or is_p or is_e or is_d):
                continue
            blob = None
            kw = False; us = False
            if is_e or is_d:
                blob = " ".join(str(v) for v in row.values())
                kw = bool(ACRO.search(blob) or PHRASE.search(blob))
                us = bool(US_ONLY.search(blob))
            # KPMG
            if is_k:
                ev, nm, ja = cur_state(exp, KPMG)
                writers["kpmg"][1].writerow(row)
                counts["kpmg"][0] += 1; counts["kpmg"][1] += nm; counts["kpmg"][2] += ja
            if is_p:
                ev, nm, ja = cur_state(exp, PWC)
                writers["pwc"][1].writerow(row)
                counts["pwc"][0] += 1; counts["pwc"][1] += nm; counts["pwc"][2] += ja
            if is_e and kw:
                ev, nm, ja = cur_state(exp, EY)
                writers["ey"][1].writerow(row)
                counts["ey"][0] += 1; counts["ey"][1] += nm; counts["ey"][2] += ja
            elif is_e and (not kw) and us:
                us_extra["ey"] += 1
            if is_d and kw:
                ev, nm, ja = cur_state(exp, dsl)
                writers["deloitte"][1].writerow(row)
                counts["deloitte"][0] += 1; counts["deloitte"][1] += nm; counts["deloitte"][2] += ja
            elif is_d and (not kw) and us:
                us_extra["deloitte"] += 1
        for cat, (fh, w) in writers.items():
            fh.close()
    return counts, us_extra, cols


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    for cat in ("kpmg", "pwc", "ey", "deloitte"):
        os.makedirs(os.path.join(TMP, cat), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"shards {len(shards)} | workers {WORKERS}", flush=True)
    tot = {k: [0, 0, 0] for k in ("kpmg", "pwc", "ey", "deloitte")}
    us_extra = {"ey": 0, "deloitte": 0}; cols = None
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for counts, ux, c in pool.imap_unordered(worker, shards):
            cols = cols or c
            for k in tot:
                for i in range(3):
                    tot[k][i] += counts[k][i]
            for k in us_extra:
                us_extra[k] += ux[k]
    # merge partials -> one CSV per category
    names = {"kpmg": "KPMG_kpmg-us.csv", "pwc": "PwC_pwc-ac-india.csv", "ey": "EY_GCC.csv", "deloitte": "Deloitte_GCC.csv"}
    for cat, fname in names.items():
        out = os.path.join(OUT_DIR, fname)
        with open(out, "w", encoding="utf-8", newline="") as fo:
            w = csv.writer(fo, quoting=csv.QUOTE_ALL); w.writerow(cols)
            for p in sorted(glob.glob(os.path.join(TMP, cat, "*.csv"))):
                with open(p, "r", encoding="utf-8", newline="") as fi:
                    for line in fi:
                        fo.write(line)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n==== BIG-4 CURATED ({time.time()-t0:,.0f}s) ====")
    lab = {"kpmg": "KPMG (kpmg-us)", "pwc": "PwC (pwc-ac-india)", "ey": "EY (ernstandyoung + GCC kw)", "deloitte": "Deloitte (deloitte* + GCC kw)"}
    for k in ("kpmg", "pwc", "ey", "deloitte"):
        e, n, j = tot[k]
        print(f"  {lab[k]:34s} profiles {e:>7,} | cur-normal {n:>7,} | cur-jani {j:>7,}")
    print(f"\n  (if standalone \"US\" were also a keyword, EY would add {us_extra['ey']:,} and Deloitte {us_extra['deloitte']:,} more)")
    print(f"  files -> {OUT_DIR}")


if __name__ == "__main__":
    main()
