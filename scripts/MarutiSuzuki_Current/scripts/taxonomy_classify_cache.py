# Purpose: Classify Maruti Suzuki currently-working profiles to the Capsight GCC taxonomy ONCE, in parallel,
#   and cache per-profile results (uid, area, L1, L2, L3_Role, L3_ID, Role_Category, how, phrase) to a CSV so
#   re-mapping / re-reporting is instant (no re-scan). Reads the exported MarutiSuzuki_current_3areas.csv.
#   AREA env optional (default all 3 areas). Uses gcc_taxonomy_classifier (library regexes, title-first).
import ast, csv, os, sys
from multiprocessing import Pool

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import gcc_taxonomy_classifier as TC

csv.field_size_limit(2 ** 31 - 1)
CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_current_3areas.csv"
CACHE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_taxonomy_cache.csv"
AREAS = {
    "Greater Delhi Area": ["greater delhi area", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad",
                           "faridabad", "manesar", "kharkhoda", "sonipat", "bahadurgarh"],
    "Greater Bengaluru Area": ["greater bengaluru area", "bengaluru", "bangalore"],
    "Pune/PCMC Area": ["pune/pimpri-chinchwad area", "pune", "pimpri", "chinchwad"],
}
COMP = None


def area_of(a):
    a = (a or "").lower()
    for name, toks in AREAS.items():
        if any(t in a for t in toks):
            return name
    return "other"


def parse(x):
    try:
        v = ast.literal_eval(x or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def init():
    global COMP
    COMP = TC.load()


def work(rec):
    uid, area, headline, summary, exp_s, skill_s = rec
    exp = parse(exp_s)
    cur = ""; past = []; descs = []
    for e in exp:
        if not isinstance(e, dict):
            continue
        t = e.get("title") or ""
        dur = e.get("duration") or {}
        is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
        if is_cur and not cur:
            cur = t
        else:
            past.append(t)
        if e.get("description"):
            descs.append(str(e.get("description")))
    skills = parse(skill_s)
    sk = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
    r = TC.classify(headline, cur, sk, " ; ".join(past), summary, " ".join(descs), COMP)
    return [uid, area, r["L1"], r["L2"], r["L3_Role"], r["L3_ID"], r["Role_Category"], r["how"],
            (r["phrase"] or "")[:40], cur[:60], (headline or "")[:60]]


def main():
    recs = []
    with open(CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ar = area_of(row.get("miniprofile_location_address"))
            recs.append((row["uid"], ar, row.get("miniprofile_headline"),
                         row.get("miniprofile_summary"), row.get("experience"), row.get("skill")))
    print(f"profiles to classify: {len(recs):,}")
    out = []
    with Pool(12, initializer=init) as pool:
        for r in pool.imap_unordered(work, recs, chunksize=200):
            out.append(r)
    with open(CACHE, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["uid", "area", "L1", "L2", "L3_Role", "L3_ID", "Role_Category", "how", "phrase",
                    "cur_title", "headline"])
        w.writerows(out)
    print(f"cached {len(out):,} -> {CACHE}")


if __name__ == "__main__":
    main()
