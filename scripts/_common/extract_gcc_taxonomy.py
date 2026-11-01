# Purpose: Read the Capsight GCC Taxonomy Library xlsx (Downloads, READ-ONLY) and extract the 669 L3 rows
#   (L3_ID, Macro_Pillar, L1, L2, L3_Role, Role_Category, is_tech, Tag_When, Excludes, Typical_Job_Titles,
#   Ambiguous_Titles, Profile_Match_Regex + text signals) to a JSON in the project for reproducible use by the
#   classifier. Validates each Profile_Match_Regex compiles. Writes nothing to Downloads.
import json, os, re
import openpyxl

SRC = r"C:\Users\LENOVO\Downloads\Capsight_GCC_Taxonomy_Library_Updated_v2 (1).xlsx"
OUT_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common\gcc_taxonomy"
OUT = os.path.join(OUT_DIR, "gcc_taxonomy_v2.json")


def main():
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb["GCC_Taxonomy_Library"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h) for h in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    keep = ["L3_ID", "Macro_Pillar", "L1_Category", "L2_Job_Family", "L3_Role", "L3_Definition",
            "Role_Category", "is_tech", "Key_Responsibilities", "Skills_&_Tools", "Tag_When",
            "Excludes", "Typical_Job_Titles", "Ambiguous_Titles", "Profile_Match_Regex"]
    out = []; bad_regex = 0
    for r in rows[1:]:
        if not r or not r[idx["L3_ID"]]:
            continue
        rec = {k: (r[idx[k]] if r[idx[k]] is not None else "") for k in keep}
        rx = str(rec["Profile_Match_Regex"] or "")
        if "\\\\" in rx:                       # 9 "Updated" rows double-escaped backslashes -> collapse
            rx = rx.replace("\\\\", "\\")
            rec["Profile_Match_Regex"] = rx
        rec["_regex_ok"] = True
        if rx:
            try:
                re.compile(rx, re.I)
            except Exception as e:
                rec["_regex_ok"] = False; bad_regex += 1
                print("BAD REGEX", rec["L3_ID"], rec["L3_Role"], "->", str(e)[:80])
        out.append(rec)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    from collections import Counter
    print(f"\nextracted {len(out)} L3 rows -> {OUT}")
    print(f"bad regexes: {bad_regex}")
    print("L1 counts:", dict(Counter(x["L1_Category"] for x in out)))
    print("rows with non-empty regex:", sum(1 for x in out if x["Profile_Match_Regex"]))


if __name__ == "__main__":
    main()
