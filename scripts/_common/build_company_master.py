# Purpose: STEP 1 of the validation project - deduplicated UNIQUE-COMPANY master list across Track-1 +
#   Track-2 + Track-2 Part-2 + recovered companies. Merges duplicate entries that refer to the same company
#   BOTH by standardized name AND by shared LinkedIn slug (union-find), so differently-named entries for one
#   company collapse into a single row. Output: one row per unique company with canonical name, the track(s)
#   it appears in, all its slugs, and a blank 'industry_L1'/'industry_L2' to be filled in Step 2 (Track-1's
#   validated sector is pre-filled where available). No profile counts here (added in the centre-mapping step).
import csv, os, re
import openpyxl

OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Master_List.csv"
T1 = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track1_CompanyResolve\final_slugs.csv"
T2 = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_CompanyResolve\final_slugs.csv"
P2 = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\final_slugs.csv"
NM = r"C:\Users\LENOVO\Downloads\Track_Company_Coverage_NotMatched (2).xlsx"
T1_XLSX = r"C:\Users\LENOVO\Downloads\Track_1_Companies (1).xlsx"
NM_TK = {"Track-1": "track1", "Track-2": "track2", "Track-2 Part-2": "part2"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def collect():
    # returns list of (track, company_name, slug)
    rows = []
    for f, col, tk in ((T1, "company", "track1"), (T2, "company_target", "track2"), (P2, "company_target", "part2")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            c = (r.get(col) or "").strip(); s = (r.get("slug") or "").strip().lower()
            if c and s:
                rows.append((tk, c, s))
    # recovered from the NotMatched file
    ws = openpyxl.load_workbook(NM, read_only=True, data_only=True)["All_NotMatched"]
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r or not (r[0] or (len(r) > 1 and r[1])):
            continue
        raw = str(r[0]).strip() if r[0] else ""; tk = NM_TK.get(raw, raw) if raw else "track1"
        comp = str(r[1]).strip() if r[1] else ""
        for cell in r[2:]:
            if cell and "linkedin.com" in str(cell):
                m = re.search(r"/(company|showcase)/([^/?#]+)", str(cell))
                if m and comp:
                    rows.append((tk, comp, m.group(2).strip().lower()))
    return rows


def t1_sectors():
    m = {}
    try:
        wb = openpyxl.load_workbook(T1_XLSX, read_only=True, data_only=True)
        for sh in ("Track 1 companies", "Track 1 in top 200"):
            if sh not in wb.sheetnames:
                continue
            it = wb[sh].iter_rows(values_only=True); hdr = [str(h) for h in next(it)]
            ci = {h: i for i, h in enumerate(hdr)}
            for r in it:
                if r and r[ci["company_name"]]:
                    m[norm(r[ci["company_name"]])] = (r[ci["sector"]] or "", r[ci["l2_industry"]] or "")
    except Exception as e:
        print("t1_sectors:", e)
    return m


def main():
    rows = collect()
    # per normalized-name: display, tracks, slugs ; and slug -> names (for union by shared slug)
    disp = {}; nm_tracks = {}; nm_slugs = {}; slug_names = {}
    for tk, comp, slug in rows:
        nn = norm(comp)
        disp.setdefault(nn, comp)
        if len(comp) > len(disp[nn]):   # prefer a longer/cleaner display name
            disp[nn] = comp
        nm_tracks.setdefault(nn, set()).add(tk)
        nm_slugs.setdefault(nn, set()).add(slug)
        slug_names.setdefault(slug, set()).add(nn)
    # union-find over normalized names, union by shared slug
    parent = {nn: nn for nn in disp}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for slug, names in slug_names.items():
        names = list(names)
        for i in range(1, len(names)):
            union(names[0], names[i])
    # build components
    comp_members = {}
    for nn in disp:
        comp_members.setdefault(find(nn), []).append(nn)
    sect = t1_sectors()
    out = []
    for root, members in comp_members.items():
        tracks = set(); slugs = set(); names = set()
        l1 = l2 = ""
        for nn in members:
            tracks |= nm_tracks[nn]; slugs |= nm_slugs[nn]; names.add(disp[nn])
            if nn in sect and sect[nn][0] and not l1:
                l1, l2 = sect[nn]
        canonical = max(names, key=len)
        out.append({
            "company": canonical,
            "aka_names": " | ".join(sorted(n for n in names if n != canonical)),
            "tracks": " | ".join(sorted(tracks)),
            "n_slugs": len(slugs),
            "slugs": " | ".join(sorted(slugs)),
            "industry_L1": l1, "industry_L2": l2,
            "L1_source": "track1_excel" if l1 else "", "status": "" if l1 else "NEEDS_INDUSTRY",
        })
    out.sort(key=lambda r: (-r["n_slugs"], r["company"].lower()))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader(); w.writerows(out)
    from collections import Counter
    tc = Counter()
    for r in out:
        for t in r["tracks"].split(" | "):
            tc[t] += 1
    pre = sum(1 for r in out if r["industry_L1"])
    print(f"unique companies (deduped): {len(out):,}")
    print(f"  appear in -> {dict(tc)} (a company in 2 tracks counts in each)")
    print(f"  industry pre-filled from Track-1 Excel: {pre:,} | still NEEDS_INDUSTRY: {len(out)-pre:,}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
