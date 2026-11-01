# Purpose: OPTION 3 resolver. For each of the 983 Track-1 company names, discover the real LinkedIn company
#   ENTITIES from the supply itself: scan passive_IN, match a role's company.NAME to a target (leading-token
#   entity-expansion), and for every match record the role's SLUG (company.lnkd_uid or /company/<slug>) +
#   domain + example name, counting distinct profiles per (target, slug). The slug bridges differently-named
#   entities (people who typed "J.P. Morgan" still carry slug jpmorganchase). Output = a REVIEW table:
#   per company, each slug with its profile count + example name + domain + the linkedin URL -> you tick the
#   real ones, then we pull profiles by the confirmed slugs. Read-only; resumable per shard.
import csv, glob, gzip, json, os, pickle, re, sys, time, unicodedata
from collections import Counter
from multiprocessing import Pool
import orjson

ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
XLSX = r"C:\Users\LENOVO\Downloads\Track_1_Companies (1).xlsx"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve"
CAND_DIR = os.path.join(OUT_DIR, "_resolve_cand")
REVIEW_CSV = os.path.join(OUT_DIR, "track1_entity_review.csv")
WORKERS = 15
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
    targets = {}
    for sheet in ("Track 1 companies", "Track 1 in top 200"):
        ws = wb[sheet]; rows = ws.iter_rows(values_only=True); hdr = next(rows); ci = list(hdr).index("company_name")
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
    return ""  # no slug


def tasks():
    out = []
    for p in POOLS:
        out += glob.glob(os.path.join(p, "*.jsonl.gz"))
    out.sort(key=os.path.getsize, reverse=True)
    return out[:LIMIT] if LIMIT else out


def main():
    os.makedirs(CAND_DIR, exist_ok=True)
    init()
    print(f"targets {len(TARGETS):,} | pools {[os.path.basename(p) for p in POOLS]}", flush=True)
    shards = tasks()
    # unique checkpoint name per source shard (folders share basenames)
    def pk(s):
        return os.path.join(CAND_DIR, os.path.basename(os.path.dirname(s)) + "__" + os.path.basename(s) + ".pkl")
    # scan_file writes by basename only; to be safe against the 58 shared basenames, qualify here:
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
    # write review CSV grouped by target, slugs by count desc
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
    print(f"\n==== RESOLVE DONE ({time.time()-t0:,.0f}s) ====")
    print(f"  distinct (target,slug) pairs: {len(cand):,}  -> {REVIEW_CSV}")


def scan_file_q(path):
    # qualified-name wrapper so checkpoints are unique across the two folders
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


if __name__ == "__main__":
    main()
