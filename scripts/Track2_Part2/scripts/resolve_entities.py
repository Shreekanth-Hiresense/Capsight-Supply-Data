# Purpose: TRACK-2 PART-2 resolver. Discover LinkedIn company slugs for each company in
#   Track2_Part2_Domestic_L3_Negation_v2 (1).xlsx (sheet 'Company - L3s to negate', col 'Company Name')
#   from the supply itself: scan passive_IN (read-only), match a role's company.NAME to a target
#   (leading-token entity-expansion), record slug + domain + example name + distinct-profile count per
#   (target, slug). Output part2_entity_review.csv. Resumable per shard. Same method as Track-1/Track-2.
import csv, glob, gzip, os, pickle, re, sys, time, unicodedata
from collections import Counter
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
XLSX = r"C:\Users\LENOVO\Downloads\Track2_Part2_Domestic_L3_Negation_v2 (1).xlsx"
SHEET = "Company - L3s to negate"
NAME_COL = "Company Name"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2"
CAND_DIR = os.path.join(OUT_DIR, "_resolve_cand")
REVIEW_CSV = os.path.join(OUT_DIR, "part2_entity_review.csv")
WORKERS = 12
LIMIT = int(os.environ["LIMIT_FILES"]) if os.environ.get("LIMIT_FILES") else None

LEGAL = {"private", "limited", "pvt", "ltd", "llp", "inc", "incorporated", "corporation", "corp",
         "llc", "gmbh", "plc", "sa", "ag", "nv", "bv", "co", "company", "holdings"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    t = s.split()
    while t and t[-1] in LEGAL:
        t.pop()
    return " ".join(t)


def build_targets():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb[SHEET]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    ci = list(hdr).index(NAME_COL)
    targets = {}
    for r in rows:
        if ci < len(r) and r[ci] and str(r[ci]).strip():
            t = norm(str(r[ci]))
            if len(t) >= 2:
                targets.setdefault(t, str(r[ci]).strip())
    return targets


TARGETS = None; LABELS = None; MAXTOK = 1


def init():
    global TARGETS, LABELS, MAXTOK
    LABELS = build_targets()
    TARGETS = set(LABELS)
    MAXTOK = max((t.count(" ") + 1 for t in TARGETS), default=1)


def matched_targets(name):
    nm = norm(name)
    if not nm:
        return ()
    toks = nm.split()
    return [" ".join(toks[:k]) for k in range(1, min(len(toks), MAXTOK) + 1) if " ".join(toks[:k]) in TARGETS]


def slug_of(company):
    uid = company.get("lnkd_uid")
    if uid:
        return str(uid).strip().lower()
    for k in ("lnkd_url1", "lnkd_url2"):
        u = company.get(k)
        if u and "/company/" in u:
            s = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s:
                return s
    return ""


def tasks():
    out = []
    for p in POOLS:
        out += glob.glob(os.path.join(p, "*.jsonl.gz"))
    out.sort(key=os.path.getsize, reverse=True)
    return out[:LIMIT] if LIMIT else out


def scan_file_q(path):
    cand = Counter(); info = {}
    with gzip.open(path, "rb") as f:
        for line in f:
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            pairs = set()
            for e in d.get("experience") or []:
                comp = e.get("company") or {}
                name = comp.get("name")
                if not name:
                    continue
                tg = matched_targets(name)
                if not tg:
                    continue
                sl = slug_of(comp); dom = (comp.get("domain") or "").lower()
                for t in tg:
                    pairs.add((t, sl))
                    info.setdefault((t, sl), [norm(name), dom])
            for p in pairs:
                cand[p] += 1
    stem = os.path.basename(os.path.dirname(path)) + "__" + os.path.basename(path)
    tmp = os.path.join(CAND_DIR, stem + ".pkl.tmp")
    with open(tmp, "wb") as fh:
        pickle.dump({"cand": dict(cand), "info": info}, fh, protocol=4)
    os.replace(tmp, os.path.join(CAND_DIR, stem + ".pkl"))
    return stem


def main():
    os.makedirs(CAND_DIR, exist_ok=True)
    init()
    print(f"targets {len(TARGETS):,} | pools {[os.path.basename(p) for p in POOLS]}", flush=True)
    shards = tasks()

    def pk(s):
        return os.path.join(CAND_DIR, os.path.basename(os.path.dirname(s)) + "__" + os.path.basename(s) + ".pkl")

    todo = [s for s in shards if not os.path.exists(pk(s))]
    print(f"shards {len(shards)} | done {len(shards)-len(todo)} | to scan {len(todo)} | workers {WORKERS}", flush=True)
    t0 = time.time()
    if todo:
        with Pool(WORKERS, initializer=init) as pool:
            for i, base in enumerate(pool.imap_unordered(scan_file_q, todo), 1):
                if i % 20 == 0 or i == len(todo):
                    print(f"  scanned {i}/{len(todo)} ({time.time()-t0:,.0f}s)", flush=True)
    cand = Counter(); info = {}
    for s in shards:
        p = pk(s)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                d = pickle.load(fh)
            cand.update(d["cand"])
            for k, v in d["info"].items():
                info.setdefault(k, v)
    by_target = {}
    for (t, sl), n in cand.items():
        by_target.setdefault(t, []).append((sl, n))
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["company_target", "company_label", "linkedin_slug", "linkedin_url",
                    "example_name", "domain", "n_profiles"])
        for t in sorted(by_target):
            for sl, n in sorted(by_target[t], key=lambda x: -x[1]):
                ex, dom = info.get((t, sl), ["", ""])
                url = ("https://www.linkedin.com/company/" + sl + "/") if sl else ""
                w.writerow([t, LABELS.get(t, t), sl, url, ex, dom, n])
    print(f"\n==== PART-2 RESOLVE DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  distinct (target,slug) pairs: {len(cand):,}  -> {REVIEW_CSV}")


if __name__ == "__main__":
    main()
