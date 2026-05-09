# UK Company Data Explorer

Browse and query 5.7 million UK companies from [Companies House](https://download.companieshouse.gov.uk/en_output.html) — entirely in your browser, no server required.

Built with [DuckDB-WASM](https://duckdb.org/docs/stable/clients/wasm/overview.html) and [Apache Parquet](https://parquet.apache.org/). Queries run locally via HTTP range requests; no data is ever uploaded anywhere.

## Pages

| Page | Description |
|---|---|
| `index.html` | SQL Explorer — run arbitrary DuckDB SQL against the full dataset |
| `treemap.html` | SIC TreeMap — hierarchical treemap of companies by industry, drill-down to company list |

## Data

The source data is the **Companies House Basic Company Data** bulk file (~2.6 GB CSV, ~5.7M rows). It is pre-processed into three Parquet chunks for GitHub Pages compatibility:

| File | Size | Rows |
|---|---|---|
| `companies_0.parquet` | ~82 MB | ~1.9M |
| `companies_1.parquet` | ~79 MB | ~1.9M |
| `companies_2.parquet` | ~81 MB | ~1.9M |

The chunks are sorted by `CompanyStatus → SICCode.SicText_1 → IncorporationDate` and compressed with ZSTD level 9, which enables DuckDB-WASM to skip row groups efficiently when filtering.

## Regenerating the Parquet files

Download the latest bulk file from [Companies House](https://download.companieshouse.gov.uk/en_output.html) and place it in `exploration/`. Then:

```bash
pip install -r requirements.txt
python build_parquet.py
```

Options:

```
--csv PATH          Path or glob to the source CSV (default: exploration/BasicCompanyData*.csv)
--chunks N          Number of output files (default: 3)
--row-group-size N  Rows per Parquet row group (default: 500000)
--compression-level N  ZSTD level 1–22 (default: 9)
```

## Running locally

Any static HTTP server works:

```bash
python -m http.server 8787
# then open http://localhost:8787
```

## Project structure

```
├── index.html           SQL Explorer
├── treemap.html         SIC TreeMap
├── sic_meta.json        SIC 2007 hierarchy (sections → subclasses)
├── build_parquet.py     Script to regenerate Parquet chunks from CSV
├── requirements.txt     Python dependencies (duckdb)
├── companies_0.parquet  } Parquet data chunks
├── companies_1.parquet  }
├── companies_2.parquet  }
└── exploration/         Local scripts and raw data (gitignored)
```

## Data licence

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
