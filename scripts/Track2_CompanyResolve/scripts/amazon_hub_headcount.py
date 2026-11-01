# Purpose: Amazon-only headcount from the Track-2 pulled set. Keep people CURRENTLY working at the Amazon
#   page (slug 'amazon') under Jani's logic (present OR start-date-but-no-end), whose location is one of the
#   7 hub cities (checked on EITHER the profile address/region OR the Amazon current-role location, with
#   city aliases), and REMOVE generic domestic-sales roles (current Amazon role title matches a sales
#   pattern). Reports the full funnel (counts at each step) for both Jani and NORMAL current logic. Read-only.
import ast, csv, glob, gzip, json, os, re, time
from multiprocessing import Pool

csv.field_size_limit(2 ** 31 - 1)
SHARD_DIR = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight\Track2_BySlug_profiles\shards"
WORKERS = 15
AMAZON_SLUGS = {"amazon"}   # main Amazon page only (AWS = amazon-web-services is separate)

# hub city -> alias tokens (substring match, lowercased)
HUBS = {
    "hyderabad": ["hyderabad", "secunderabad"],
    "mumbai": ["mumbai", "navi mumbai", "thane"],
    "chennai": ["chennai"],
    "bengaluru": ["bengaluru", "bangalore"],
    "pune": ["pune"],
    "delhi ncr": ["delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad"],
    "coimbatore": ["coimbatore"],
}
HUB_TOKENS = [tok for toks in HUBS.values() for tok in toks]

# generic domestic-sales title patterns (word-boundary where sensible)
SALES_RE = re.compile(
    r"\b(sales|business development|account manager|account executive|territory|"
    r"relationship manager|field sales|inside sales|channel sales|sales development|"
    r"area sales|regional sales|sales executive|sales associate|sales officer)\b", re.I)


def slug_from_url(u):
    if not u or "/company/" not in u:
        return None
    return (u.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()) or None


def role_slugs(c):
    s = set()
    if c.get("lnkd_uid"):
        s.add(str(c["lnkd_uid"]).strip().lower())
    for k in ("lnkd_url1", "lnkd_url2"):
        sl = slug_from_url(c.get(k))
        if sl:
            s.add(sl)
    return s


def hub_hit(text):
    t = (text or "").lower()
    return any(tok in t for tok in HUB_TOKENS)


def worker(path):
    # counters: ever, cur(jani), cur+loc, cur+loc-sales  (and same for normal)
    c = {"ever": 0, "j_cur": 0, "j_loc": 0, "j_final": 0, "n_cur": 0, "n_loc": 0, "n_final": 0}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                exp = ast.literal_eval(row.get("experience") or "[]")
            except Exception:
                try:
                    exp = json.loads(row.get("experience") or "[]")
                except Exception:
                    exp = []
            if not isinstance(exp, list):
                continue
            prof_loc = (row.get("miniprofile_location_address") or "") + " " + (row.get("miniprofile_location_region") or "")
            prof_hub = hub_hit(prof_loc)
            is_ever = False
            # per current-amazon-role flags
            j_cur = n_cur = False
            j_loc = n_loc = False
            j_final = n_final = False
            for e in exp:
                if not isinstance(e, dict):
                    continue
                if not (role_slugs(e.get("company") or {}) & AMAZON_SLUGS):
                    continue
                is_ever = True
                dur = e.get("duration") or {}
                present = bool(dur.get("present")); end = dur.get("end"); start = dur.get("start")
                is_j = present or ((not end) and start)      # Jani current
                is_n = present                                 # normal current
                if not (is_j or is_n):
                    continue
                loc_ok = prof_hub or hub_hit(e.get("location") or "")
                title = e.get("title") or ""
                not_sales = not SALES_RE.search(title)
                if is_j:
                    j_cur = True
                    if loc_ok:
                        j_loc = True
                        if not_sales:
                            j_final = True
                if is_n:
                    n_cur = True
                    if loc_ok:
                        n_loc = True
                        if not_sales:
                            n_final = True
            if is_ever:
                c["ever"] += 1
                c["j_cur"] += j_cur; c["j_loc"] += j_loc; c["j_final"] += j_final
                c["n_cur"] += n_cur; c["n_loc"] += n_loc; c["n_final"] += n_final
    return c


def main():
    shards = sorted(glob.glob(os.path.join(SHARD_DIR, "*.csv.gz")))
    print(f"amazon slugs {AMAZON_SLUGS} | shards {len(shards)} | workers {WORKERS}", flush=True)
    tot = {"ever": 0, "j_cur": 0, "j_loc": 0, "j_final": 0, "n_cur": 0, "n_loc": 0, "n_final": 0}
    t0 = time.time()
    with Pool(WORKERS) as pool:
        for c in pool.imap_unordered(worker, shards):
            for k in tot:
                tot[k] += c[k]
    print(f"\n==== AMAZON (page 'amazon') HUB HEADCOUNT ({time.time()-t0:,.0f}s) ====")
    print(f"  hubs: Hyderabad, Mumbai, Chennai, Bengaluru, Pune, Delhi NCR, Coimbatore")
    print(f"  ever worked at Amazon (distinct)                 : {tot['ever']:,}")
    print(f"\n  -- JANI current logic --")
    print(f"  currently working at Amazon                      : {tot['j_cur']:,}")
    print(f"  ...and in a hub city                             : {tot['j_loc']:,}")
    print(f"  ...and NOT generic domestic sales (FINAL)        : {tot['j_final']:,}")
    print(f"     (removed as generic sales: {tot['j_loc']-tot['j_final']:,})")
    print(f"\n  -- NORMAL current logic (duration.present) --")
    print(f"  currently working at Amazon                      : {tot['n_cur']:,}")
    print(f"  ...and in a hub city                             : {tot['n_loc']:,}")
    print(f"  ...and NOT generic domestic sales (FINAL)        : {tot['n_final']:,}")
    print(f"     (removed as generic sales: {tot['n_loc']-tot['n_final']:,})")


if __name__ == "__main__":
    main()
