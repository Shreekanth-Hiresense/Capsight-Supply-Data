# Purpose: L3 (job-function) breakdown of the Greater Delhi Area Maruti Suzuki currently-working profiles,
#   using the WHOLE profile (headline + current title + skills + past titles + summary + descriptions) via
#   function_classifier.classify(). Prints the function distribution (KEEP functions + excluded) and a few
#   example assignments per function for sanity-check. Reads the already-exported CSV; no dump scan.
import ast, csv, sys
from collections import Counter, defaultdict

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\_common")
from function_classifier import classify, KEEP

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
    dist = Counter(); n = 0
    samples = defaultdict(list)
    with open(CSV, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if not in_delhi(r.get("miniprofile_location_address")):
                continue
            n += 1
            exp = parse(r.get("experience"))
            cur_title = ""; past = []; descs = []
            for e in exp:
                if not isinstance(e, dict):
                    continue
                t = e.get("title") or ""
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                if is_cur and not cur_title:
                    cur_title = t
                else:
                    past.append(t)
                if e.get("description"):
                    descs.append(str(e.get("description")))
            skills = parse(r.get("skill"))
            skills_text = " ; ".join(s if isinstance(s, str) else str(s) for s in skills)
            fn, keep, score, ev = classify(
                r.get("miniprofile_headline"), cur_title, skills_text,
                " ; ".join(past), r.get("miniprofile_summary"), " ".join(descs))
            dist[fn] += 1
            if len(samples[fn]) < 4:
                samples[fn].append((r.get("miniprofile_headline") or "")[:60] + "  ||  cur='" + cur_title[:40] + "'")
    kept = sum(v for f, v in dist.items() if f in KEEP)
    print(f"Greater Delhi Area profiles classified: {n:,}")
    print(f"KEEP (one of the 11 functions): {kept:,}  |  excluded/unknown: {n-kept:,}\n")
    print("---- L3 / function distribution ----")
    for fn, v in dist.most_common():
        tag = "KEEP " if fn in KEEP else "drop "
        print(f"  {tag}{fn:32s} {v:>6,}  ({100*v/n:4.1f}%)")
    print("\n---- sample assignments (headline || current title) ----")
    for fn, v in dist.most_common():
        print(f"\n[{fn}]")
        for s in samples[fn]:
            print("   ", s)


if __name__ == "__main__":
    main()
