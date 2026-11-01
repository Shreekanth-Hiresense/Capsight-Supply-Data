# Purpose: SINGLE SOURCE OF TRUTH for all Jani Big-4 / Track curation rules. Every reporting script
#   (top_companies.py, company_entity_scan.py, etc.) imports from here so the rules are applied
#   CONSISTENTLY and never revert. Slug-level rules also live in each track's final_slugs.csv (which is
#   edited to match); this module holds the rules that need code (keyword gates, connection thresholds,
#   excluded companies).
#
# RULES (as instructed by the user, 2026-10-28):
#   KPMG      -> only slug kpmg-us                         (enforced in final_slugs)
#   PwC       -> only slug pwc-ac-india                    (enforced in final_slugs)
#   EY        -> only profiles with a GCC keyword anywhere (enforced here: GATED_COMPANIES + keyword)
#   Deloitte  -> only profiles with a GCC keyword anywhere (enforced here)
#   Sankalp Semiconductor (= hcltech page) -> NOT a company; excluded (removed from final_slugs; EXCLUDE_COMPANIES)
#   Bosch     -> parked for a future track; NOT in Track-1 (removed from final_slugs)
#   Walmart   -> drop wal-mart-canada / walmart-ca / junk (enforced in final_slugs)
#   PepsiCo   -> drop pepsico-middleeast (enforced in final_slugs)
#   Connections: Track-1 & Track-2 keep >=10 (shards_min10conn); Microsoft keeps >=20
#   "(no slug)" is never an entity (can't be pulled). Currently-working default = JANI (present OR start-no-end).
import re

# companies whose profiles count ONLY if a GCC/offshore keyword appears anywhere in the profile
GATED_COMPANIES = {"ey", "deloitte"}

# companies to ignore entirely even if a slug slips into final_slugs
EXCLUDE_COMPANIES = {"sankalp semiconductor"}

# per-company connection floor (default 10); Microsoft is 20
CONN_FLOOR_DEFAULT = 10
CONN_FLOOR = {"microsoft": 20}

_ACRO = re.compile(r"\b(?:GDS|GBS|GSS|GDC|GCC|USI|KGS|SSC)\b", re.I)
_PHRASE = re.compile(
    r"global delivery services|global business services|global shared services|"
    r"global capability centre|global capability center|global delivery centre|global delivery center|"
    r"shared services centre|shared services center|acceleration centre|acceleration center|"
    r"global operations|centre of excellence|center of excellence", re.I)


def has_gcc_keyword(blob):
    return bool(_ACRO.search(blob) or _PHRASE.search(blob))


def gated(company):
    return (company or "").strip().lower() in GATED_COMPANIES


def excluded(company):
    return (company or "").strip().lower() in EXCLUDE_COMPANIES
