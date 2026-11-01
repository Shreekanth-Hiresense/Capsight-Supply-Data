# Purpose: Per-track company COVERAGE audit for GitHub/validation. For each track, compare the INPUT company
#   list (the source Excel) against the resolver output (entity_review: which companies got a real LinkedIn
#   page/slug). A company "did not match" = no non-junk slug was found for it in the supply. Companies we
#   excluded on purpose (from NOT_analyzed_companies.csv) are labelled separately. Writes ONE Excel with a
#   Summary sheet (counts per track) + one sheet per track listing the not-matched companies. Read-only inputs.
import csv, os, re
import openpyxl
from openpyxl.styles import Font

DOWN = r"C:\Users\LENOVO\Downloads"
RES = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track_Company_Coverage_NotMatched.xlsx"
NOT_AN = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\NOT_analyzed_companies.csv"
JUNK = {"", "(no-slug)", "results", "forage", "none", "no-slug"}

TRACKS = [
    ("Track-1", os.path.join(DOWN, "Track_1_Companies (1).xlsx"), "Track 1 companies", "company_name",
     os.path.join(RES, r"Track1_CompanyResolve\track1_entity_review.csv")),
    ("Track-2", os.path.join(DOWN, "Track2_Confirmed_GCC_Locations_pART 1.xlsx"), "High confidence only",
     "Company Name", os.path.join(RES, r"Track2_CompanyResolve\track2_entity_review.csv")),
    ("Track-2 Part-2", os.path.join(DOWN, "Track2_Part2_Domestic_L3_Negation_v2 (1).xlsx"),
     "Company - L3s to negate", "Company Name", os.path.join(RES, r"Track2_Part2\part2_entity_review.csv")),
]


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def input_companies(xlsx, sheet, col):
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb[sheet]
    it = ws.iter_rows(values_only=True)
    hdr = [str(h) if h is not None else "" for h in next(it)]
    ci = hdr.index(col)
    out = []
    for r in it:
        if ci < len(r) and r[ci] not in (None, ""):
            out.append(str(r[ci]).strip())
    return out


def matched_targets(review):
    m = set()
    for r in csv.DictReader(open(review, encoding="utf-8")):
        sl = (r.get("linkedin_slug") or "").strip().lower()
        if sl and sl not in JUNK:
            m.add(norm(r.get("company_target")))
            m.add(norm(r.get("company_label")))
    return m


def excluded_set():
    ex = {}
    if os.path.exists(NOT_AN):
        for r in csv.DictReader(open(NOT_AN, encoding="utf-8")):
            if "exclud" in (r.get("reason") or "").lower():
                ex[norm(r.get("company"))] = r.get("track", "")
    return ex


def main():
    excl = excluded_set()
    wb = openpyxl.Workbook()
    summ = wb.active; summ.title = "Summary"
    summ.append(["Track", "Input companies", "Matched (LinkedIn page found)",
                 "Did NOT match (no page)", "Excluded on purpose"])
    for c in summ[1]:
        c.font = Font(bold=True)
    allnm = wb.create_sheet("All_NotMatched")      # consolidated list of every no-page company
    allnm.append(["#", "Track", "Company"])
    for c in allnm[1]:
        c.font = Font(bold=True)
    all_rows = []
    for name, xlsx, sheet, col, review in TRACKS:
        comps = input_companies(xlsx, sheet, col)
        seen = set(); uniq = []
        for c in comps:
            if norm(c) not in seen:
                seen.add(norm(c)); uniq.append(c)
        matched = matched_targets(review)
        no_page = []; excluded = []
        for c in uniq:
            n = norm(c)
            if n in matched:
                continue
            if n in excl:
                excluded.append(c)
            else:
                no_page.append(c)
        summ.append([name, len(uniq), len(uniq) - len(no_page) - len(excluded), len(no_page), len(excluded)])
        for c in no_page:
            all_rows.append((name, c))
        ws = wb.create_sheet(name.replace(" ", "_")[:31])
        ws.append(["company", "status"])
        ws["A1"].font = ws["B1"].font = Font(bold=True)
        for c in no_page:
            ws.append([c, "no LinkedIn page found"])
        for c in excluded:
            ws.append([c, "excluded on purpose"])
        print(f"{name}: input {len(uniq)} | matched {len(uniq)-len(no_page)-len(excluded)} | "
              f"no-page {len(no_page)} | excluded {len(excluded)}")
    for i, (trk, c) in enumerate(all_rows, 1):
        allnm.append([i, trk, c])
    print(f"\nAll_NotMatched sheet: {len(all_rows)} companies total")
    wb.save(OUT)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
