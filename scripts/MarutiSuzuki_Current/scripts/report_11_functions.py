# Purpose: Map the cached Capsight-taxonomy classification (MarutiSuzuki_taxonomy_cache.csv) to the user's 11
#   target functions and report the breakdown WITHIN those 11 only. Routing is by L1 + L2 (see MAP). Everything
#   not in the 11 (Operations & Supply Chain, Legal/Risk, Admin/Facilities, sales-support/pre-sales/market-
#   access/category, Strategy & Leadership, UX design, OUT_OF_SCOPE, NOISE) is reported separately as excluded.
#   AREA env optional (e.g. "Greater Delhi Area") to restrict. Instant (reads the cache).
import csv, os, sys
from collections import Counter

csv.field_size_limit(2 ** 31 - 1)
CACHE = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_taxonomy_cache.csv"
AREA = os.environ.get("AREA", "").strip()

ACC_L2 = {"accounting & controllership", "payables, receivables & payroll", "tax",
          "audit, controls & regulatory reporting"}
CONSULT_L2 = {"consulting & transformation", "research & advisory"}
PPM_L2 = {"business project management", "it delivery management", "portfolio management & pmo",
          "business analysis"}
MKT_L2 = {"marketing", "content, communications & creative"}
RESEARCH_L2 = {"discovery & laboratory research", "product & formulation development"}


def bucket(L1, L2, L3):
    l1 = (L1 or "").strip(); l2 = (L2 or "").strip().lower()
    if l1 == "Engineering":
        return "Engineering"
    if l1 == "Technology":
        return "Information Technology"
    if l1 == "Human Resources":
        return "Human Resources"
    if l1 == "Customer Service & Success":
        return "Product Mgmt + Cust Service/Support"
    if l1 == "Product & Design":
        return "Product Mgmt + Cust Service/Support" if "product management" in l2 else None
    if l1 == "Finance & Accounting":
        return "Accounting" if l2 in ACC_L2 else "Finance"
    if l1 == "Strategy, Consulting & Program Management":
        if l2 in CONSULT_L2:
            return "Consulting"
        if l2 in PPM_L2:
            return "Program and Project Management"
        return None   # Strategy & Leadership -> excluded
    if l1 == "Sales & Marketing":
        return "Marketing" if l2 in MKT_L2 else None   # sales support / pre-sales / etc excluded
    if l1 == "Clinical, Scientific & Regulatory":
        return "Research" if l2 in RESEARCH_L2 else None
    return None


ORDER = ["Engineering", "Information Technology", "Finance", "Accounting", "Human Resources",
         "Program and Project Management", "Marketing", "Consulting", "Research",
         "Product Mgmt + Cust Service/Support", "Business Development"]


def main():
    keep = Counter(); excl = Counter(); how_in = Counter(); n = 0
    with open(CACHE, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if AREA and r["area"] != AREA:
                continue
            n += 1
            b = bucket(r["L1"], r["L2"], r["L3_Role"])
            if b:
                keep[b] += 1; how_in[r["how"]] += 1
            else:
                lbl = r["L1"] if r["L1"] in ("NOISE", "OUT_OF_SCOPE") else f"{r['L1']} / {r['L2']}"
                excl[lbl] += 1
    scope = AREA or "ALL 3 AREAS"
    tot_keep = sum(keep.values())
    print(f"=== Maruti Suzuki currently-working — {scope} — within the 11 functions ===")
    print(f"profiles considered: {n:,}  |  IN the 11 functions: {tot_keep:,}  |  excluded: {n-tot_keep:,}")
    print(f"(of the in-11, matched via: {dict(how_in)})\n")
    for b in ORDER:
        print(f"  {b:38s} {keep.get(b,0):>6,}")
    print("\n--- excluded (not in your 11), top buckets ---")
    for lbl, c in excl.most_common(15):
        print(f"  {c:>6,}  {lbl}")


if __name__ == "__main__":
    main()
