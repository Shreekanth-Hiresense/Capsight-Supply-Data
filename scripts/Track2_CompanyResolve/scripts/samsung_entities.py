# Purpose: Per-entity (slug) ever-worked + currently-working (Jani) counts for Track-2 Samsung, over the live
#   Track-2 >=20 set (shards_min20conn). Mirrors the Part-2 Samsung table. Distinct uids per slug (a person at
#   2 slugs counts in each, like the Part-2 per-entity view). Read-only. Currently-working (Jani) = a role at
#   the slug with duration.present OR (start set AND no end). NO function filter (Track-2 isn't function-filtered).
import ast, csv, glob, gzip, json, os, sys, time
from collections import defaultdict
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARDS = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards_min20conn"
SLUGS = ["samsung-electronics", "samsungrndindiabangalore", "samsungmobile",
         "samsung-engineering-india", "samsungena"]
SL = set(SLUGS)


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
        v = ast.literal_eval(x or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        try:
            return json.loads(x or "[]")
        except Exception:
            return []


def worker(path):
    ever = defaultdict(int); cur = defaultdict(int)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            exp = parse(row.get("experience"))
            hit_ever = set(); hit_cur = set()
            for e in exp:
                if not isinstance(e, dict):
                    continue
                hits = role_slugs(e.get("company") or {}) & SL
                if not hits:
                    continue
                hit_ever |= hits
                dur = e.get("duration") or {}
                if bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start")):
                    hit_cur |= hits
            for s in hit_ever:
                ever[s] += 1
            for s in hit_cur:
                cur[s] += 1
    return ever, cur


def main():
    shards = sorted(glob.glob(os.path.join(SHARDS, "*.csv.gz")))
    print(f"Track-2 shards {len(shards)} | slugs {SLUGS}", flush=True)
    EVER = defaultdict(int); CUR = defaultdict(int); t0 = time.time()
    with Pool(10) as pool:
        for ever, cur in pool.imap_unordered(worker, shards):
            for s, n in ever.items():
                EVER[s] += n
            for s, n in cur.items():
                CUR[s] += n
    print(f"\n==== Track-2 Samsung entities ({time.time()-t0:,.0f}s) ====")
    print(f"  {'entity (slug)':28s} {'ever':>8s} {'cur-Jani':>10s}")
    for s in SLUGS:
        print(f"  {s:28s} {EVER.get(s,0):>8,} {CUR.get(s,0):>10,}")


if __name__ == "__main__":
    main()
