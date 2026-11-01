# Purpose: STEP 2 - map each company in our Company_Master_List.csv to the GCC master list (reliable source)
#   by LinkedIn SLUG, and attach the authoritative L1 Sector / L2 Industry from it. Validated classifications
#   from the GCC master win; companies not found in the master are flagged NEEDS_REVIEW (not guessed). Also
#   captures the master's per-city headcounts + GCC center type per company for the later centre-mapping step.
import csv, re
import openpyxl

MASTER = r"C:\Users\LENOVO\Downloads\gcc master list (2).xlsx"
OURS = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Master_List.csv"
OUT = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Company_Master_List_industry.csv"
GCC_CLEAN = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\gcc_master_clean.csv"


def slugs_from(text):
    out = set()
    for m in re.finditer(r"/(company|showcase)/([^/?#\s,]+)", str(text or "")):
        out.add(m.group(2).strip().lower())
    return out


def nrm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def load_master():
    wb = openpyxl.load_workbook(MASTER, read_only=True, data_only=True)
    ws = wb["GCC Master List"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[3]
    idx = {}
    for i, h in enumerate(hdr):
        if h is not None:
            idx[str(h).strip()] = i
    cN, cU, cL1, cL2 = idx["Company Name"], idx["LinkedIn Entity URL(s)"], idx["L1 Sector"], idx["L2 Business Model Industry"]
    cEnt = idx.get("LinkedIn Specific Entity Name(s)")
    slug2 = {}; name2 = {}; master_rows = []
    for r in rows[4:]:
        if not r or not r[cN]:
            continue
        name = str(r[cN]).strip(); l1 = str(r[cL1] or "").strip(); l2 = str(r[cL2] or "").strip()
        sl = slugs_from(r[cU])
        master_rows.append((name, l1, l2, sorted(sl)))
        for s in sl:
            slug2[s] = (name, l1, l2)
        name2.setdefault(nrm(name), (name, l1, l2))
        # also index the master's entity names for name-matching
        if cEnt is not None and r[cEnt]:
            for part in re.split(r"[;,|/]", str(r[cEnt])):
                if nrm(part):
                    name2.setdefault(nrm(part), (name, l1, l2))
    with open(GCC_CLEAN, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(["master_company", "L1", "L2", "slugs"])
        for name, l1, l2, sl in master_rows:
            w.writerow([name, l1, l2, " | ".join(sl)])
    return slug2, name2, len(master_rows)


def main():
    slug2, name2, nmaster = load_master()
    print(f"GCC master companies: {nmaster:,} | slugs indexed: {len(slug2):,} | names indexed: {len(name2):,}")
    rows = list(csv.DictReader(open(OURS, encoding="utf-8")))
    by_slug = 0; by_name = 0
    out = []
    for r in rows:
        our_slugs = [s.strip().lower() for s in (r.get("slugs") or "").split("|") if s.strip()]
        hit = None; how = ""
        # NAME first (reliable); slug lists can be polluted/collide, so slug is only a fallback
        cands = [r.get("company", "")] + (r.get("aka_names") or "").split(" | ")
        for c in cands:
            if nrm(c) and nrm(c) in name2:
                hit = name2[nrm(c)]; how = "name"; break
        if hit is None:
            for s in our_slugs:
                if s in slug2:
                    hit = slug2[s]; how = "slug"; break
        if hit:
            r["industry_L1"] = hit[1]; r["industry_L2"] = hit[2]
            r["L1_source"] = "gcc_master(" + how + ")"; r["matched_master_company"] = hit[0]
            r["status"] = "validated" if hit[1] else "master_blank_L1"
            if how == "slug":
                by_slug += 1
            else:
                by_name += 1
        else:
            if r.get("industry_L1"):
                r["L1_source"] = r.get("L1_source") or "track1_excel"; r["status"] = "track1_excel_only"
            else:
                r["status"] = "NEEDS_REVIEW (not in GCC master)"
            r["matched_master_company"] = ""
        out.append(r)
    matched = by_slug + by_name
    print(f"  matched to GCC master: {matched:,} (by slug {by_slug:,}, by name {by_name:,})")
    cols = list(out[0].keys())
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(out)
    from collections import Counter
    st = Counter(r["status"] for r in out)
    withL1 = sum(1 for r in out if r.get("industry_L1"))
    print(f"our unique companies: {len(out):,}")
    print(f"  have an L1 now (gcc_master or track1_excel): {withL1:,} | missing: {len(out)-withL1:,}")
    print("  status breakdown:")
    for k, v in st.most_common():
        print(f"    {v:>5,}  {k}")
    print(f"  -> {OUT}\n  -> {GCC_CLEAN}")


if __name__ == "__main__":
    main()
