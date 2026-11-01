# Purpose: On the small recovered Part-2 set (Recovered_part2_profiles.csv), compute the currently-working
#   (Jani) count that falls in the user's 11 functions (intern-drop + Capsight 11-function filter) -- the same
#   rule as the rest of Part-2, done AFTER the pull (not inline) for speed. Needs the matched company per row,
#   so it re-derives the Part-2 company from each profile's experience slugs vs the missed-file slug map.
import ast, csv, os, re, sys
from collections import Counter

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts")
sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import part2_negation as P2
import gcc_taxonomy_classifier as TC

csv.field_size_limit(2 ** 31 - 1)
SRC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Recovered_part2_profiles.csv"
XLSX = r"C:\Users\LENOVO\Downloads\Track_Company_Coverage_NotMatched (2).xlsx"


def part2_slugs():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["All_NotMatched"]
    s = set()
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r or str(r[0]).strip() != "Track-2 Part-2":
            continue
        for c in r[2:]:
            if c and "linkedin.com" in str(c):
                m = re.search(r"/(company|showcase)/([^/?#]+)", str(c))
                if m:
                    s.add(m.group(2).strip().lower())
    return s


def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v, list) else []
    except Exception:
        return []


def role_slugs(c):
    out = set()
    if c.get("lnkd_uid"):
        out.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        u = c.get(k)
        if u and "/company/" in u:
            sl = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if sl:
                out.add(sl)
    return out


def main():
    P2SLUGS = part2_slugs()
    COMP = TC.load()
    total = cur = cur_intern_ok = kept = 0
    func = Counter()
    with open(SRC, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            exp = parse(row.get("experience"))
            titles = []; cur_title = ""; past = []; descs = []; is_cur_at_p2 = False
            for e in exp:
                if not isinstance(e, dict):
                    continue
                t = e.get("title") or ""
                dur = e.get("duration") or {}
                isc = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if isc and not cur_title:
                    cur_title = t
                else:
                    past.append(t)
                if e.get("description"):
                    descs.append(str(e.get("description")))
                if role_slugs(e.get("company") or {}) & P2SLUGS:
                    titles.append(t)
                    if isc:
                        is_cur_at_p2 = True
            if not is_cur_at_p2:
                continue
            cur += 1
            if P2.INTERN.search(" ; ".join(titles)):
                continue
            cur_intern_ok += 1
            skills = parse(row.get("skill"))
            sk = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
            res = TC.classify(row.get("miniprofile_headline"), cur_title, sk, " ; ".join(past),
                              row.get("miniprofile_summary"), " ".join(descs), COMP)
            b = TC.map_to_user11(res["L1"], res["L2"], res["L3_Role"])
            if b:
                kept += 1; func[b] += 1
    print(f"recovered Part-2 profiles: {total:,}")
    print(f"  currently-working (Jani) at a recovered Part-2 page: {cur:,}")
    print(f"  after intern-drop: {cur_intern_ok:,}")
    print(f"  KEPT in the 11 functions: {kept:,}")
    print("  by function:")
    for k, v in func.most_common():
        print(f"    {k:38s} {v:>7,}")


if __name__ == "__main__":
    main()
