# Purpose: Classify a ziplabs supply profile to the Capsight GCC taxonomy (L1/L2/L3) using the library's own
#   Profile_Match_Regex, following the sheet's tagging rules:
#     1) run every L3 regex against the TITLE (current title + headline); if several match, the LONGEST matched
#        phrase wins -> that L3.
#     2) if no title match, run the regexes against the TEXT blob (skills + experience descriptions + summary +
#        past titles); longest match wins.
#     3) if still nothing: domestic role (front-line sales/BD, retail, teaching, shop-floor/plant, on-site
#        trades, drivers, warehouse) -> OUT_OF_SCOPE; unusable -> NOISE.
#   Returns dict(L1,L2,L3_Role,L3_ID,Role_Category,how,phrase). NOTE v1 does not yet apply each L3's Excludes /
#   site-vs-office scope text (so office-vs-plant Engineering split is approximate for manufacturers).
import os, re

# Source of truth = the user's Capsight Excel, read directly (user instruction 2026-10-29).
XLSX = r"C:\Users\LENOVO\Downloads\Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx"

OUT_OF_SCOPE = re.compile(
    r"(?i)(?<![a-z])("
    r"field sales|inside sales|channel sales|key account|relationship manager|territory|area sales|"
    r"regional sales|sales executive|sales officer|sales manager|business development|lead generation|"
    r"retail|showroom|dealer|cashier|store manager|hospitality|waiter|patient care|nurse|pharmacist|"
    r"pharmacy|teacher|lecturer|professor|faculty|tuition|shop floor|production operator|machine operator|"
    r"plant operator|assembly line|welder|fitter|technician|electrician|driver|delivery|warehouse|"
    r"site engineer|site supervisor|resident engineer|construction|commissioning|security guard"
    r")(?![a-z])")


# ---- map a taxonomy (L1,L2) to the user's 11 target functions (None = not in the 11) ----
_ACC_L2 = {"accounting & controllership", "payables, receivables & payroll", "tax",
           "audit, controls & regulatory reporting"}
_CONSULT_L2 = {"consulting & transformation", "research & advisory"}
_PPM_L2 = {"business project management", "it delivery management", "portfolio management & pmo",
           "business analysis"}
_MKT_L2 = {"marketing", "content, communications & creative"}
_RESEARCH_L2 = {"discovery & laboratory research", "product & formulation development"}
USER_11 = ["Engineering", "Information Technology", "Finance", "Accounting", "Human Resources",
           "Program and Project Management", "Marketing", "Consulting", "Research",
           "Product Mgmt + Cust Service/Support", "Business Development"]


def map_to_user11(L1, L2, L3=None):
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
        return "Accounting" if l2 in _ACC_L2 else "Finance"
    if l1 == "Strategy, Consulting & Program Management":
        if l2 in _CONSULT_L2:
            return "Consulting"
        if l2 in _PPM_L2:
            return "Program and Project Management"
        return None
    if l1 == "Sales & Marketing":
        return "Marketing" if l2 in _MKT_L2 else None
    if l1 == "Clinical, Scientific & Regulatory":
        return "Research" if l2 in _RESEARCH_L2 else None
    return None


def load():
    # Read the Capsight Excel directly; fix the 9 double-escaped regexes; compile each L3's Profile_Match_Regex.
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["GCC_Taxonomy_Library"]
    it = ws.iter_rows(values_only=True)
    hdr = [str(h) for h in next(it)]
    idx = {h: i for i, h in enumerate(hdr)}
    compiled = []
    for r in it:
        if not r or not r[idx["L3_ID"]]:
            continue
        rx = str(r[idx["Profile_Match_Regex"]] or "")
        if "\\\\" in rx:
            rx = rx.replace("\\\\", "\\")
        if not rx:
            continue
        rec = {"L3_ID": r[idx["L3_ID"]], "L1_Category": r[idx["L1_Category"]],
               "L2_Job_Family": r[idx["L2_Job_Family"]], "L3_Role": r[idx["L3_Role"]],
               "Role_Category": r[idx["Role_Category"]]}
        try:
            compiled.append((re.compile(rx, re.I), rec))
        except Exception:
            continue
    return compiled


def _best(text, compiled):
    best = None; best_len = 0
    for rx, r in compiled:
        m = rx.search(text)
        if m and len(m.group(0)) > best_len:
            best_len = len(m.group(0)); best = r; best_phrase = m.group(0)
    if best is None:
        return None
    return best, best_phrase


def classify(headline, cur_title, skills_text, past_titles, summary, desc_text, compiled):
    title_text = f"{cur_title or ''}  {headline or ''}".strip()
    hit = _best(title_text, compiled)
    how = "title"
    if hit is None:
        blob = "  ".join(x for x in (skills_text, desc_text, summary, past_titles) if x)
        hit = _best(blob, compiled); how = "text"
    if hit is None:
        blob2 = "  ".join(x for x in (title_text, skills_text, past_titles, summary) if x)
        if OUT_OF_SCOPE.search(blob2):
            return {"L1": "OUT_OF_SCOPE", "L2": "OUT_OF_SCOPE", "L3_Role": "OUT_OF_SCOPE",
                    "L3_ID": "", "Role_Category": "", "how": "domestic", "phrase": ""}
        return {"L1": "NOISE", "L2": "NOISE", "L3_Role": "NOISE", "L3_ID": "",
                "Role_Category": "", "how": "none", "phrase": ""}
    r, phrase = hit
    return {"L1": r["L1_Category"], "L2": r["L2_Job_Family"], "L3_Role": r["L3_Role"],
            "L3_ID": r["L3_ID"], "Role_Category": r["Role_Category"], "how": how, "phrase": phrase}
