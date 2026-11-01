# Purpose: Probe the 4 confirmed Maruti Suzuki slugs across the full India dump (read-only). For profiles with
#   a role at any of the 4 slugs: tally per-slug ever/cur-jani, and the DISTRIBUTION of location strings
#   (miniprofile.location.address + .region) so we can map the user's 4 location labels (Greater Delhi Area,
#   Greater Bengaluru Area, Pune/Pimpri-Chinchwad Area, Pune District) to what is really stored. No export yet.
import glob, gzip, os, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
import orjson

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ZIP_ROOT = r"C:\Users\LENOVO\Downloads\hiresense_data_ziplabs"
POOLS = sorted(glob.glob(os.path.join(ZIP_ROOT, "ziplabs_passive_IN_*")))
SLUGS = {"maruti-udyog-limited", "maruti-suzuki-innovation",
         "suzuki-research-and-development-center-india", "suzuki-digital-private-limited"}
PRE = tuple(s.encode() for s in SLUGS)
WORKERS = 12


def slugs_of(c):
    out = set()
    u = c.get("lnkd_uid")
    if u:
        out.add(str(u).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        v = c.get(k)
        if v and "/company/" in v:
            s = v.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s:
                out.add(s)
    return out


def worker(path):
    ever = defaultdict(set); cur = defaultdict(set)
    addr = Counter(); region = Counter()
    with gzip.open(path, "rb") as f:
        for line in f:
            if not any(p in line for p in PRE):
                continue
            try:
                d = orjson.loads(line)
            except Exception:
                continue
            uid = d.get("uid")
            hitany = False; curany = False
            for e in d.get("experience") or []:
                hit = slugs_of(e.get("company") or {}) & SLUGS
                if not hit:
                    continue
                hitany = True
                dur = e.get("duration") or {}
                is_cur = bool(dur.get("present")) or ((not dur.get("end")) and dur.get("start"))
                for s in hit:
                    ever[s].add(uid)
                    if is_cur:
                        cur[s].add(uid); curany = True
            if hitany:
                loc = ((d.get("miniprofile") or {}).get("location") or {})
                a = (loc.get("address") or "").strip()
                r = (loc.get("region") or "").strip()
                if curany:                      # location vocab only for currently-working
                    addr[a] += 1; region[r] += 1
    return ever, cur, addr, region


def main():
    shards = []
    for p in POOLS:
        shards += glob.glob(os.path.join(p, "*.jsonl.gz"))
    shards.sort(key=os.path.getsize, reverse=True)
    print(f"slugs {SLUGS}\nshards {len(shards)} | workers {WORKERS}", flush=True)
    EVER = defaultdict(set); CUR = defaultdict(set); ADDR = Counter(); REG = Counter()
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for ever, cur, addr, reg in pool.imap_unordered(worker, shards):
            for s, u in ever.items():
                EVER[s] |= u
            for s, u in cur.items():
                CUR[s] |= u
            ADDR.update(addr); REG.update(reg)
    allev = set(); allcur = set()
    for u in EVER.values():
        allev |= u
    for u in CUR.values():
        allcur |= u
    print(f"\n==== Maruti 4-slug totals ({time.time()-t0:,.0f}s) ====")
    for s in SLUGS:
        print(f"  {len(EVER.get(s,())):>7,} ever | {len(CUR.get(s,())):>7,} cur-jani | {s}")
    print(f"  DISTINCT: {len(allev):,} ever | {len(allcur):,} cur-jani (across the 4)")
    print("\n---- top 40 location.address among currently-working ----")
    for a, n in ADDR.most_common(40):
        print(f"  {n:>6,}  {a!r}")
    print("\n---- top 25 location.region among currently-working ----")
    for r, n in REG.most_common(25):
        print(f"  {n:>6,}  {r!r}")


if __name__ == "__main__":
    main()
