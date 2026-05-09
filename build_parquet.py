"""
build_parquet.py
================
Regenerates the three parquet chunks (companies_0/1/2.parquet) used by the
web app from the raw Companies House bulk CSV.

Usage
-----
    python exploration/build_parquet.py
    python exploration/build_parquet.py --csv path/to/BasicCompanyData*.csv
    python exploration/build_parquet.py --chunks 3 --row-group-size 500000

The output files are written to the project root so they are picked up by
index.html and treemap.html without any path changes.

Optimisation notes
------------------
- Data is sorted by CompanyStatus → SICCode.SicText_1 → IncorporationDate.
  This clusters Active companies together and groups SIC codes, so DuckDB-WASM
  can skip whole row groups when filtering (predicate pushdown via min/max stats).
- Row group size of 500 000 rows (~20 MB compressed per group, 4 groups per file)
  balances HTTP range-request overhead against selective-scan efficiency.
- ZSTD level 9 maximises compression ratio (smaller download) with negligible
  impact on decompression speed compared to lower levels.
"""

import argparse
import glob
import os
import sys
import time

import duckdb


DEFAULT_CSV_GLOB = "exploration/BasicCompanyData*.csv"
OUTPUT_DIR = "."          # project root — served directly by GitHub Pages
CHUNKS = 3
ROW_GROUP_SIZE = 500_000  # rows per row group
COMPRESSION = "ZSTD"
COMPRESSION_LEVEL = 9

SORT_COLS = [
    "CompanyStatus",
    '"SICCode.SicText_1"',
    "IncorporationDate",
]


def find_csv(path_or_glob: str) -> str:
    if os.path.isfile(path_or_glob):
        return path_or_glob
    matches = sorted(glob.glob(path_or_glob))
    if not matches:
        sys.exit(
            f"No CSV found matching '{path_or_glob}'.\n"
            "Pass --csv with the path to the Companies House bulk data file."
        )
    if len(matches) > 1:
        print(f"Warning: multiple CSVs matched, using {matches[-1]}", file=sys.stderr)
    return matches[-1]


def main():
    parser = argparse.ArgumentParser(description="Build optimised parquet chunks from Companies House CSV.")
    parser.add_argument("--csv", default=DEFAULT_CSV_GLOB, help="Path or glob to the source CSV file")
    parser.add_argument("--chunks", type=int, default=CHUNKS, help="Number of output files (default: 3)")
    parser.add_argument("--row-group-size", type=int, default=ROW_GROUP_SIZE, help="Rows per parquet row group")
    parser.add_argument("--compression-level", type=int, default=COMPRESSION_LEVEL, help="ZSTD compression level (1–22)")
    args = parser.parse_args()

    csv_path = find_csv(args.csv)
    print(f"Source CSV : {csv_path}")
    print(f"Output dir : {os.path.abspath(OUTPUT_DIR)}")
    print(f"Chunks     : {args.chunks}")
    print(f"Row group  : {args.row_group_size:,} rows")
    print(f"Compression: {COMPRESSION} level {args.compression_level}")
    print()

    t_total = time.perf_counter()
    con = duckdb.connect()

    # ── 1. Count rows ──────────────────────────────────────────────────────────
    print("Counting rows…", end=" ", flush=True)
    t0 = time.perf_counter()
    total = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{csv_path}', ignore_errors=true)").fetchone()[0]
    print(f"{total:,} rows  ({time.perf_counter()-t0:.1f}s)")

    chunk_size = (total + args.chunks - 1) // args.chunks  # ceiling division

    # ── 2. Create a sorted view of the CSV ────────────────────────────────────
    sort_clause = ", ".join(f"{c} ASC NULLS LAST" for c in SORT_COLS)
    con.execute(f"""
        CREATE VIEW source AS
        SELECT * FROM read_csv_auto('{csv_path}', ignore_errors=true)
        ORDER BY {sort_clause}
    """)

    # ── 3. Write each chunk ────────────────────────────────────────────────────
    sizes = []
    for i in range(args.chunks):
        offset = i * chunk_size
        out = os.path.join(OUTPUT_DIR, f"companies_{i}.parquet")
        print(f"Writing companies_{i}.parquet (rows {offset:,}–{min(offset+chunk_size, total)-1:,})…", end=" ", flush=True)
        t0 = time.perf_counter()
        con.execute(f"""
            COPY (
                SELECT * FROM source
                LIMIT {chunk_size} OFFSET {offset}
            )
            TO '{out}' (
                FORMAT PARQUET,
                COMPRESSION '{COMPRESSION}',
                COMPRESSION_LEVEL {args.compression_level},
                ROW_GROUP_SIZE {args.row_group_size}
            )
        """)
        elapsed = time.perf_counter() - t0
        size_mb = os.path.getsize(out) / 1024 / 1024
        sizes.append(size_mb)
        print(f"{size_mb:.1f} MB  ({elapsed:.1f}s)")

    # ── 4. Summary ─────────────────────────────────────────────────────────────
    print()
    total_mb = sum(sizes)
    print(f"Done in {time.perf_counter()-t_total:.1f}s")
    print(f"Total size: {total_mb:.1f} MB across {args.chunks} files ({total_mb/args.chunks:.1f} MB avg)")
    files_over_100 = [f"companies_{i}.parquet" for i, s in enumerate(sizes) if s > 100]
    if files_over_100:
        print(f"\nWarning: the following files exceed GitHub's 100 MB limit: {files_over_100}")
    else:
        print("All files are under the 100 MB GitHub limit. ✓")


if __name__ == "__main__":
    main()
