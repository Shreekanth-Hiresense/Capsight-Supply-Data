# Purpose: Disk-space guard that MUST be called before (and after) every CSV/Excel export in this
# project. The C: drive on this machine is 476 GB and has hit 100% full more than once; a full-dump
# export can be several GB, and a crash mid-write leaves a corrupt half-file. This module makes the
# check one line, prints a human-readable warning, and can hard-refuse an export that would not fit.
#
# Usage:
#     from disk_guard import check_disk, warn_after_write
#     check_disk(estimated_gb=3.5, label="ML_Engineer headline export")   # before opening the file
#     ...write the CSV...
#     warn_after_write(path)                                             # after closing it
#
# Thresholds (free space AFTER the estimated write):
#     < 5 GB   -> CRITICAL, raises DiskSpaceError unless force=True
#     < 20 GB  -> WARNING, prints loudly and returns False
#     >= 20 GB -> OK
#
# Never deletes anything. Freeing space is always the user's decision.

import os
import shutil

CRITICAL_GB = 5.0
WARN_GB = 20.0


class DiskSpaceError(RuntimeError):
    """Raised when an export would leave the drive critically full."""


def _fmt(gb):
    return f"{gb:,.1f} GB"


def disk_stats(path="C:\\"):
    """Return (total_gb, used_gb, free_gb, pct_used) for the drive holding `path`."""
    drive = os.path.splitdrive(os.path.abspath(path))[0] or "C:"
    total, used, free = shutil.disk_usage(drive + "\\")
    g = 1024 ** 3
    return total / g, used / g, free / g, 100.0 * used / total


def check_disk(estimated_gb=0.0, label="export", path="C:\\", force=False, quiet=False):
    """Check free space before writing. Returns True if comfortable, False if it is a warning.

    Raises DiskSpaceError when the write would leave less than CRITICAL_GB free (unless force).
    `estimated_gb` is the expected size of what is about to be written — pass a real estimate
    (rows * bytes-per-row) whenever one is available; 0.0 still reports current free space.
    """
    total, used, free, pct = disk_stats(path)
    after = free - estimated_gb

    head = f"[disk] {label}: {_fmt(free)} free of {_fmt(total)} ({pct:.0f}% used)"
    if estimated_gb:
        head += f" | writing ~{_fmt(estimated_gb)} -> ~{_fmt(after)} left"

    if after < CRITICAL_GB:
        msg = (f"{head}\n"
               f"[disk] CRITICAL: this export would leave under {_fmt(CRITICAL_GB)} free. "
               f"Refusing to start. Free space first — do NOT auto-delete the user's "
               f"deliverables; ask which files can go.")
        if not force:
            raise DiskSpaceError(msg)
        print(msg + "\n[disk] force=True — proceeding anyway.")
        return False

    if after < WARN_GB:
        print(f"{head}\n"
              f"[disk] WARNING: under {_fmt(WARN_GB)} would remain after this write. "
              f"Tell the user the current free space before continuing, and prefer writing "
              f"only the columns actually needed.")
        return False

    if not quiet:
        print(head)
    return True


def estimate_csv_gb(rows, bytes_per_row=2500):
    """Rough size estimate for a full-column export from this dataset.

    ~2,500 bytes/row is the measured ballpark once the stringified experience/education/skill
    columns are included. Pass a smaller value for slim exports (uid+url+headline is ~200).
    """
    return rows * bytes_per_row / (1024 ** 3)


def warn_after_write(path, label=None):
    """Report the size actually written and the free space left. Call after closing the file."""
    label = label or os.path.basename(path)
    size_gb = os.path.getsize(path) / (1024 ** 3) if os.path.exists(path) else 0.0
    total, used, free, pct = disk_stats(path)
    print(f"[disk] wrote {label}: {_fmt(size_gb)} | {_fmt(free)} free of {_fmt(total)} "
          f"({pct:.0f}% used)")
    if free < WARN_GB:
        print(f"[disk] WARNING: under {_fmt(WARN_GB)} free after this write.")
    return size_gb


if __name__ == "__main__":
    total, used, free, pct = disk_stats()
    print(f"C: {_fmt(free)} free of {_fmt(total)} ({pct:.0f}% used)")
    for rows in (100_000, 1_000_000, 5_000_000):
        print(f"  {rows:>9,} rows full-column export ~= {_fmt(estimate_csv_gb(rows))}")
