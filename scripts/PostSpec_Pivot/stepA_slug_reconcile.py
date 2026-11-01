
# STEP A: company-first slug reconciliation + benchmark-eligibility flag + re-pull list.
# Pure analysis over existing files (GCC master Excel + Company_Master_List_industry.csv). No dump scan.
import csv, re, os, sys
import openpyxl
sys.stdout.reconfigure(encoding="utf-8", errors="replace"); csv.field_size_limit(2**31-1)
JC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
MASTER_XLSX = r"C:\Users\LENOVO\Downloads\gcc master list (2).xlsx"
OURS = os.path.join(JC, "Company_Master_List_industry.csv")
OUT = os.path.join(JC, "StepA_slug_reconciliation.csv")

def nrm(s): return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()
def slugs_from(txt):
    out = set()
    for m in re.findall(r"/company/([^/\s,|]+)", str(txt or "")):
        out.add(m.strip().lower())
    return out

# --- load master ---
wb = openpyxl.load_workbook(MASTER_XLSX, read_only=True, data_only=True)
ws = wb["GCC Master List"]
rows = list(ws.iter_rows(values_only=True))
hdr = rows[3]
# locate key columns by header text
def col(sub):
    for i, c in enumerate(hdr):
        if str(c or "").strip().lower().startswith(sub.lower()):
            return i
    return None
C_NAME = 1; C_SPECIFIC = 2; C_URL = 3
C_HQSTATE = col("Global HQ State"); C_HQCITY = col("Global HQ City"); C_TOTAL = col("Total Calibrated India")

master = {}          # norm_name -> dict
master_slug2name = {}
for r in rows[4:]:
    nm = str(r[C_NAME] or "").strip()
    if not nm: continue
    sl = slugs_from(r[C_SPECIFIC]) | slugs_from(r[C_URL])
    hq_state = str(r[C_HQSTATE] or "")
    hq_city = str(r[C_HQCITY] or "")
    india_hq = ("india" in hq_state.lower()) or ("india" in hq_city.lower())
    try: tot = int(r[C_TOTAL]) if r[C_TOTAL] not in (None, "") else None
    except Exception: tot = None
    rec = {"name": nm, "slugs": sl, "india_hq": india_hq, "total": tot}
    master[nrm(nm)] = rec
    for s in sl: master_slug2name.setdefault(s, nrm(nm))

print(f"master companies: {len(master):,} | india-HQ: {sum(1 for m in master.values() if m['india_hq']):,}")

# --- load ours ---
our = list(csv.DictReader(open(OURS, encoding="utf-8")))
def our_slugs(row): return set(s.strip().lower() for s in (row.get("slugs") or "").split("|") if s.strip())

n_inmaster = n_indhq = n_notinmaster = n_missingpage = 0
repull_pages = 0
with open(OUT, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["our_company", "tracks", "our_status", "matched_master", "match_how", "in_master",
                "india_hq", "benchmark_eligible", "reason", "master_slugs", "our_slugs",
                "missing_master_slugs(re-pull)", "extra_our_slugs(review/pollution)", "master_india_total"])
    for row in our:
        comp = row["company"]; n = nrm(comp)
        osl = our_slugs(row)
        mm = (row.get("matched_master_company") or "").strip()
        rec = None; how = ""
        if mm and nrm(mm) in master:
            rec = master[nrm(mm)]; how = "matched_master_company"
        if rec is None and n in master:
            rec = master[n]; how = "name"
        if rec is None:
            for a in (row.get("aka_names") or "").split("|"):
                if nrm(a) in master: rec = master[nrm(a)]; how = "alias"; break
        if rec is None:
            shared = {master_slug2name[s] for s in osl if s in master_slug2name}
            if len(shared) == 1:
                rec = master[next(iter(shared))]; how = "slug"
        in_master = rec is not None
        india_hq = bool(rec and rec["india_hq"])
        if not in_master:
            elig = "No"; reason = "not in GCC master (service-provider/absent)"; n_notinmaster += 1
        elif india_hq:
            elig = "No"; reason = "Indian-HQ (not a foreign captive)"; n_indhq += 1
        else:
            elig = "Yes"; reason = ""; n_inmaster += 1
        msl = rec["slugs"] if rec else set()
        missing = sorted(msl - osl)       # master pages we never pulled
        extra = sorted(osl - msl)         # our pages not master-authoritative (sibling or pollution -> review)
        if in_master and missing:
            n_missingpage += 1; repull_pages += len(missing)
        w.writerow([comp, row.get("tracks",""), row.get("status","")[:22], rec["name"] if rec else "",
                    how, in_master, india_hq, elig, reason, " | ".join(sorted(msl)), " | ".join(sorted(osl)),
                    " | ".join(missing), " | ".join(extra), rec["total"] if rec else ""])

print(f"our companies: {len(our):,}")
print(f"  benchmark-eligible (foreign captive, in master): {n_inmaster:,}")
print(f"  EXCLUDED Indian-HQ: {n_indhq:,}")
print(f"  EXCLUDED not-in-master: {n_notinmaster:,}")
print(f"  companies missing >=1 master page (re-pull): {n_missingpage:,} | total master pages to re-pull: {repull_pages:,}")
print(f"-> {OUT}")
