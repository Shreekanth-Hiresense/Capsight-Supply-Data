# "CURRENTLY WORKING" — use the JANI logic ONLY

⚠️ **This project uses the JANI definition of "currently working" everywhere. Do NOT use the "normal"
present-only definition.** Using the wrong one will silently change every current-count in the project.

## The JANI logic (v2) — THE ONE TO USE
A role counts as **current** if:

```python
def is_current_role_JANI(e):
    dur = e.get("duration") or {}
    start = dur.get("start")
    end   = dur.get("end")
    return dur.get("present") is True or (bool(start) and not end)
```

In words: **`duration.present` is True, OR the role has a `duration.start` and NO `duration.end`.**
(The "start set and no end" branch is what makes it broader than the normal definition — it catches ongoing
roles LinkedIn didn't explicitly flag `present`.)

A person can have more than one current role; for a single "current employer" pick the present/ongoing role
with the latest `duration.start`.

## The "normal" logic — DO NOT USE HERE (shown only so you can tell them apart)
```python
# NORMAL (present-only) — NOT used in this project
def is_current_role_NORMAL(e):
    dur = e.get("duration") or {}
    return dur.get("present") is True or "present" in (e.get("date1") or "").lower()
```
The normal definition is `present` only. It is the default elsewhere on this machine, which is exactly why it
is easy to pick up by mistake. **For anything in this project, always use the JANI logic above.**

## Where this is already implemented
The shared engine `scripts/_common/jani_rules.py` is the single source of truth for the curation rules; the
counting/finalize scripts import from it. When you write new code, reuse that logic rather than re-deriving it.

## Other standing rules that travel with "current" (summary — full detail in the documentation §6)
- **Connection floor:** tracks are filtered to ≥20 connections (blanks removed). Microsoft / Google / Amazon
  require ≥35 (applied at count time).
- **EY / Deloitte** profiles count only if the profile contains a GCC/offshore keyword (GDS, GBS, GCC, USI,
  "Global Capability Centre", etc.) — the gate lives in `jani_rules.py`.
- **11-function filter** (Capsight taxonomy) is applied to **currently-working only**, NEVER to ever-worked;
  and (in the done work) only to Track-2 Part-2 + Maruti, not to Track-1/Track-2.
- **Never delete a multi-company person** — exclude a company by dropping its slug / not crediting it, keep
  the person for their other real companies.
