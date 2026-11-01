# Purpose: Capsight GCC taxonomy (L1/L2/L3) breakdown of the Maruti Suzuki Greater Delhi Area currently-working
#   profiles, using gcc_taxonomy_classifier (the library's own Profile_Match_Regex, longest-match-wins, title
#   first then text, else OUT_OF_SCOPE/NOISE). Reads the exported CSV; no dump scan. Prints L1 distribution,
#   L2 within each L1, and top L3 roles, plus how-matched (title/text/domestic) and sample assignments.
import ast, csv, sys
from collections import Counter, defaultdict

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
import gcc_taxonomy_classifier as TC

csv.field_size_limit(2 ** 31 - 1)
CSV = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\MarutiSuzuki_current_3areas.csv"
DELHI = ["greater delhi area", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad",
         "faridabad", "manesar", "kharkhoda", "sonipat", "bahadurgarh"]


def in_delhi(a):
    a = (a or "").lower()
    return any(t in a for t in DELHI)


def parse(x):
    try:
        v = ast.literal_eval(x or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    compiled = TC.load()
    print(f"taxonomy regexes loaded: {len(compiled)}")
    L1 = Counter(); L2 = defaultdict(Counter); L3 = Counter(); HOW = Counter()
    samp = defaultdict(list); n = 0
    with open(CSV, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if not in_delhi(r.get("miniprofile_location_address")):
                continue
            n += 1
            exp = parse(r.get("experience"))
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
            skills = parse(r.get("skill"))
            sk = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
            res = TC.classify(r.get("miniprofile_headline"), cur, sk, " ; ".join(past),
                              r.get("miniprofile_summary"), " ".join(descs), compiled)
            L1[res["L1"]] += 1; L2[res["L1"]][res["L2"]] += 1; HOW[res["how"]] += 1
            L3[(res["L1"], res["L3_Role"])] += 1
            key = res["L1"]
            if len(samp[key]) < 3:
                samp[key].append(f"cur='{cur[:34]}' | hl='{(r.get('miniprofile_headline') or '')[:34]}' -> "
                                 f"{res['L3_Role'][:32]} [{res['how']}:{res['phrase'][:18]}]")
    print(f"\nGreater Delhi Area profiles: {n:,}   (matched via: {dict(HOW)})\n")
    print("==== L1 FUNCTION breakdown ====")
    for k, v in L1.most_common():
        print(f"  {k:46s} {v:>6,}  ({100*v/n:4.1f}%)")
    print("\n==== L2 within each L1 (top) ====")
    for l1, _ in L1.most_common():
        if l1 in ("NOISE",):
            continue
        tops = " | ".join(f"{k} {v:,}" for k, v in L2[l1].most_common(6))
        print(f"  [{l1}]  {tops}")
    print("\n==== top 25 L3 roles ====")
    for (l1, role), v in L3.most_common(25):
        print(f"  {v:>5,}  {role:42s} <{l1}>")
    print("\n==== sample assignments per L1 ====")
    for l1, _ in L1.most_common():
        print(f"\n[{l1}]")
        for s in samp[l1]:
            print("   ", s)


if __name__ == "__main__":
    main()
