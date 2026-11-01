# Purpose: STEP A cleaning for a raw ziplabs (supply_query.py) export. The ziplabs dump has no
# is_deleted column and (per CLAUDE.md PART 9.2) no duplicate uids within the documented dump, but
# the currently-active passive pool structure is different from what PART 9.2 measured, and a single
# search can still legitimately re-match the same person via more than one OR'd term. This dedups by
# uid, keeping the row with the latest updated_at, and OVERWRITES the export in place (PART 5 STEP A).
# Reusable across every JD's ziplabs exports — lives in JD\_common\scripts per the folder rules.
#
# Usage: python dedup_ziplabs_uid.py <path_to_export.csv>

import csv
import os
import sys

import duckdb

csv.field_size_limit(2 ** 31 - 1)


def clean(path):
    tmp = path + ".dedup_tmp.csv"
    con = duckdb.connect()

    total = con.execute(
        f"SELECT COUNT(*) FROM read_csv_auto('{path}', all_varchar=true)"
    ).fetchone()[0]

    con.execute(f"""
        COPY (
            SELECT * EXCLUDE (rn) FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY uid ORDER BY updated_at DESC
                ) AS rn
                FROM read_csv_auto('{path}', all_varchar=true)
            )
            WHERE rn = 1
        ) TO '{tmp}' (FORMAT csv, FORCE_QUOTE *)
    """)

    kept = con.execute(
        f"SELECT COUNT(*) FROM read_csv_auto('{tmp}', all_varchar=true)"
    ).fetchone()[0]
    con.close()

    os.replace(tmp, path)
    print(f"uid dedup: {total:,} -> {kept:,} ({total - kept:,} duplicate uid rows removed)")
    return total, kept


if __name__ == "__main__":
    clean(sys.argv[1])
