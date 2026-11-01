# Purpose: FULL city distribution of JPMorgan Chase currently-working (Jani) profiles over the Track-1 >=20 set
#   (shards_min20conn). Shows every canon-city (metro-grouped, same canon_city as the normalization), so we can
#   see which cities are primary (>=5% & >=10) vs which fall into the excluded bucket. Read-only.
import ast, csv, glob, gzip, json, os, sys, time
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\scripts\Track2_Part2\scripts")
import part2_negation as P2
csv.field_size_limit(2 ** 31 - 1)
SHARDS = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track1_BySlug_profiles\shards_min20conn"
SLUGS = {"chase", "jpmorgan", "jpmorganchase"}


def role_slugs(c):
    s = set()
    if c.get("lnkd_uid"):
        s.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        u = c.get(k)
        if u and "/company/" in u:
            sl = u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if sl:
                s.add(sl)
    return s


def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v, list) else []
    except Exception:
        return []


def worker(path):
    c = Counter()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cur = False
            for e in parse(row.get("experience")):
                if not isinstance(e, dict):
                    continue
                if not (role_slugs(e.get("company") or {}) & SLUGS):
                    continue
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    cur = True; break
            if cur:
                loc = ((row.get("miniprofile_location_address") or "") + " "
                       + (row.get("miniprofile_location_region") or "")).lower()
                c[P2.canon_city(loc) or "(unknown city)"] += 1
    return c


def main():
    shards = sorted(glob.glob(os.path.join(SHARDS, "*.csv.gz")))
    print(f"shards {len(shards)} | JPMorgan slugs {SLUGS}", flush=True)
    C = Counter(); t0 = time.time()
    with Pool(10) as p:
        for c in p.imap_unordered(worker, shards):
            C.update(c)
    total = sum(C.values())
    print(f"\nJPMorgan Chase currently-working (Jani): {total:,}  ({time.time()-t0:,.0f}s)")
    print(f"  {'city':20s} {'count':>8} {'share':>7}  primary?(>=5% & >=10)")
    for city, n in C.most_common():
        prim = "PRIMARY" if (n >= 10 and n >= 0.05 * total) else ""
        print(f"  {city:20s} {n:>8,} {100*n/total:6.1f}%  {prim}")


if __name__ == "__main__":
    main()
