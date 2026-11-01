
# STEP B: company-first page (slug) validation. Scan our OWN pulled profiles once; for each company slug,
# measure what company LinkedIn actually shows on the roles at that slug, and classify keep / drop / review.
#   name_match_fraction = share of role-occurrences on the slug whose company.name shares a meaningful token
#   with the owning company (name + aka + matched_master).  keep >=0.60 ; drop <0.20 ; else REVIEW.
# READ-ONLY sources. Counts are role-occurrence based (approx distinct) -- enough for keep/drop decisions.
import ast, csv, glob, gzip, os, re, sys, time, unicodedata
from collections import Counter, defaultdict
from multiprocessing import Pool
csv.field_size_limit(2**31-1); sys.stdout.reconfigure(encoding="utf-8", errors="replace")
JC = r"C:\Shree\Shreekanth-Hiresense\Jani Capsight"
OUTDIR = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(JC, "Company_Master_List_industry.csv")
INPUTS = [os.path.join(JC, r"Track1_BySlug_profiles\shards_min20conn"),
          os.path.join(JC, r"Track2_BySlug_profiles\shards_min20conn"),
          os.path.join(JC, r"Track2_Part2_profiles\shards")]
RECOVERED = [os.path.join(JC, f) for f in ("Recovered_track1_profiles.csv","Recovered_track2_profiles.csv","Recovered_part2_profiles.csv")]
WORKERS = 10

STOP = {"india","indian","technologies","technology","services","service","global","solutions","solution",
        "private","limited","ltd","inc","incorporated","corporation","corp","group","company","co","pvt",
        "llp","llc","international","systems","system","labs","lab","digital","consulting","holdings",
        "enterprises","ventures","the","and","of","for","pvt.","center","centre","gcc","gic","capability"}
def _deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c))
def toks(s):
    # unicode-normalized; keep short brand tokens (EY, BT, GE, HP, AT&T->at/t) len>=2
    return set(t for t in re.sub(r"[^a-z0-9]+"," ",_deaccent(s).lower()).split() if len(t)>=2)
def sig(s):
    t = toks(s) - STOP
    return t or toks(s)   # fall back to full tokens if name is all-generic

SLUG2CO = {}; CO_EXPECT = {}; CO_FS = {}; TOKEN2COS = defaultdict(set)
def init():
    global SLUG2CO, CO_EXPECT, CO_FS, TOKEN2COS
    SLUG2CO = {}; CO_EXPECT = {}; CO_FS = {}; TOKEN2COS = defaultdict(set)
    for r in csv.DictReader(open(MASTER, encoding="utf-8")):
        comp = r["company"]
        exp = sig(comp) | sig(r.get("aka_names","")) | sig(r.get("matched_master_company",""))
        CO_EXPECT[comp] = exp; CO_FS[comp] = frozenset(exp)
        for t in exp: TOKEN2COS[t].add(comp)
        for s in (r.get("slugs") or "").split("|"):
            s = s.strip().lower()
            if s: SLUG2CO[s] = comp

def other_company_match(dsig, owner):
    """If the display-name tokens FULLY contain some OTHER master company's name tokens, return that company
    (the best / most-specific). Signals real cross-company contamination."""
    best = None; best_n = 0
    cands = set()
    for t in dsig:
        cands |= TOKEN2COS.get(t, set())
    for c in cands:
        if c == owner: continue
        fs = CO_FS.get(c)
        if fs and len(fs) >= 1 and fs <= dsig and len(fs) > best_n:
            best = c; best_n = len(fs)
    return best

def slugs_of(c):
    out = set(); u = c.get("lnkd_uid")
    if u: out.add(str(u).strip().lower())
    for k in ("lnkd_url1","lnkd_url2"):
        v = c.get(k)
        if v and "/company/" in v:
            s = v.rstrip("/").split("/company/")[-1].split("/")[0].strip().lower()
            if s: out.add(s)
    return out
def parse(x):
    try:
        v = ast.literal_eval(x or "[]"); return v if isinstance(v,list) else []
    except Exception: return []
def opener(p): return gzip.open(p,"rt",encoding="utf-8",newline="") if p.endswith(".gz") else open(p,"rt",encoding="utf-8",newline="")

def worker(path):
    allset = set(SLUG2CO.keys())
    slug_total = Counter()                         # slug -> role occurrences
    slug_names = defaultdict(Counter)              # slug -> Counter(role company.name)
    with opener(path) as f:
        for row in csv.DictReader(f):
            try:
                conn = int(float((row.get("miniprofile_connections") or "").strip()))
            except Exception: conn = None
            if conn is None or conn < 20: continue
            for e in parse(row.get("experience")):
                if not isinstance(e,dict): continue
                c = e.get("company") or {}
                if not isinstance(c,dict): continue
                sl = slugs_of(c) & allset
                if not sl: continue
                nm = (c.get("name") or "").strip()[:60]
                for s in sl:
                    slug_total[s] += 1
                    if nm: slug_names[s][nm] += 1
    return dict(slug_total), {k:dict(v) for k,v in slug_names.items()}

def main():
    import pickle
    init(); t0=time.time()
    CACHE=os.path.join(OUTDIR,"stepB_scan_cache.pkl")
    if os.environ.get("USE_CACHE") and os.path.exists(CACHE):
        with open(CACHE,"rb") as fh: TOT,NAMES = pickle.load(fh)
        TOT=Counter(TOT); NAMES=defaultdict(Counter,{k:Counter(v) for k,v in NAMES.items()})
        print(f"loaded scan cache ({len(TOT):,} slugs) - skipping scan", flush=True)
    else:
        tasks=[]
        for d in INPUTS: tasks += sorted(glob.glob(os.path.join(d,"*.csv.gz")))
        tasks += [p for p in RECOVERED if os.path.exists(p)]
        print(f"StepB scan: {len(tasks)} inputs | slugs {len(SLUG2CO):,} | workers {WORKERS}", flush=True)
        TOT=Counter(); NAMES=defaultdict(Counter); done=0
        with Pool(WORKERS, initializer=init) as pool:
            for st,sn in pool.imap_unordered(worker, tasks):
                for k,v in st.items(): TOT[k]+=v
                for k,d in sn.items():
                    for nm,n in d.items(): NAMES[k][nm]+=n
                done+=1
                if done%100==0: print(f"  {done}/{len(tasks)} | {time.time()-t0:.0f}s", flush=True)
        with open(CACHE,"wb") as fh: pickle.dump((dict(TOT),{k:dict(v) for k,v in NAMES.items()}),fh)

    dec=os.path.join(OUTDIR,"StepB_slug_decisions.csv")
    rev=os.path.join(OUTDIR,"StepB_review_bucket.csv")
    # per company, mark primary slug (largest)
    comp_slugs=defaultdict(list)
    for s,co in SLUG2CO.items(): comp_slugs[co].append(s)
    primary={}
    for co,ss in comp_slugs.items():
        if ss: primary[co]=max(ss,key=lambda s:TOT.get(s,0))
    # DEFAULT KEEP (our track pages are trusted). Only flag a page when its dominant LinkedIn name clearly
    # belongs to a DIFFERENT master company (real cross-company pollution). Primary page always kept.
    rows=[]
    for s,co in SLUG2CO.items():
        tot=TOT.get(s,0); names=NAMES.get(s,{})
        exp=CO_EXPECT.get(co,set())
        match=sum(n for nm,n in names.items() if sig(nm)&exp)
        frac=(match/tot) if tot else 0.0
        is_primary = (s==primary.get(co))
        # dominant display name
        dom = max(names.items(), key=lambda kv:kv[1])[0] if names else ""
        dsig = sig(dom)
        slug_corrob = bool(toks(s) & exp)                 # the slug itself matches the company name
        other = None if (is_primary or frac>=0.5 or slug_corrob or dsig&exp) else other_company_match(dsig, co)
        if tot==0: decision="empty(no profiles)"; other=None
        elif is_primary or frac>=0.5 or slug_corrob or (dsig&exp): decision="keep"
        elif other: decision="suspected_pollution"      # dominant name = a different known company
        else: decision="review_unclear"                  # name doesn't match owner or any known co
        top=sorted(names.items(),key=lambda kv:-kv[1])[:3]
        rows.append((co,s,tot,round(frac,3),decision, other or "", is_primary,
                     "; ".join(f"{nm}({n})" for nm,n in top)))
    rows.sort(key=lambda r:(r[0], -r[2]))
    HDR=["company","slug","profiles(approx)","name_match_frac","decision","looks_like_company","is_primary","top_role_company_names"]
    with open(dec,"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(HDR); w.writerows(rows)
    with open(rev,"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(HDR)
        w.writerows([r for r in rows if r[4] in ("suspected_pollution","review_unclear")])

    from collections import Counter as C
    dc=C(r[4] for r in rows)
    pol_vol=sum(r[2] for r in rows if r[4]=="suspected_pollution")
    unc_vol=sum(r[2] for r in rows if r[4]=="review_unclear")
    print("\nDECISIONS:", dict(dc))
    print(f"  suspected_pollution pages (dominant name = a DIFFERENT known company): profiles(approx) {pol_vol:,}")
    print(f"  review_unclear pages (name matches neither owner nor any known co): profiles(approx) {unc_vol:,}")
    print(f"-> {dec}\n-> {rev}\nDONE {time.time()-t0:.0f}s", flush=True)

if __name__=="__main__": main()
