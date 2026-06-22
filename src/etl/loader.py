"""
loader.py

ETL entry point for the Nifty 100 Financial Intelligence Platform.

Reads all 12 Excel source files, normalises company_id and year fields,
removes duplicates, validates schemas, and loads into nifty100.db (SQLite).

Run directly:  python src/etl/loader.py
Makefile:      make load

Data file facts (verified from  Excel files):
  Core files    :header=1  (row 0 is metadata, row 1 is real column headers)
  Supp files    :header=0  (standard Excel layout)
  companies.xlsx  : 92 rows   | PK = id (NSE ticker)
  profitandloss   : 1,276 rows | PK = (company_id, year)
  balancesheet    : 1,312 rows | PK = (company_id, year)
  cashflow        : 1,187 rows | PK = (company_id, year)
  analysis        : 20 rows   | Partial coverage (~8 companies)
  documents       : 1,585 rows| Partial coverage (~75 companies)
  prosandcons     : 16 rows   | Partial coverage (~8 companies)
  sectors         : 92 rows   | Full coverage
  stock_prices    : 5,520 rows| Full coverage (SIMULATED)
  market_cap      : 552 rows  | Full coverage (SIMULATED)
  financial_ratios: 1,184 rows| Computed KPIs
  peer_groups     : 56 rows   | 46/92 companies
"""

import os
import sys
import sqlite3
import logging
import time
import csv
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

#  Project root on sys.path so sibling imports work
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.etl.normaliser import normalize_year, normalize_ticker

#  Load .env 
load_dotenv(ROOT / ".env")

#  Logging 
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("etl.loader")

#  Paths 
DB_PATH        = ROOT / os.getenv("DB_PATH",                "data/nifty100.db")
RAW_DIR        = ROOT / os.getenv("RAW_DATA_DIR",           "data/raw")
SUPPORTING_DIR = ROOT / os.getenv("SUPPORTING_DATA_DIR",    "data/supporting")
OUTPUT_DIR     = ROOT / os.getenv("OUTPUT_DIR",             "output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOAD_AUDIT_PATH = OUTPUT_DIR / "load_audit.csv"
VALIDATION_PATH = OUTPUT_DIR / "validation_failures.csv"

#  Tables with (company_id, year) composite PK 
TIME_SERIES_TABLES = {
    "profitandloss", "balancesheet", "cashflow",
    "analysis", "financial_ratios",
}

#  File registry 
# (filename, table_name, header_row, file_type)
CORE_FILES = [
    ("companies.xlsx",     "companies",     1, "core"),
    ("profitandloss.xlsx", "profitandloss", 1, "core"),
    ("balancesheet.xlsx",  "balancesheet",  1, "core"),
    ("cashflow.xlsx",      "cashflow",      1, "core"),
    ("analysis.xlsx",      "analysis",      1, "core"),
    ("documents.xlsx",     "documents",     1, "core"),
    ("prosandcons.xlsx",   "prosandcons",   1, "core"),
]

SUPPLEMENTARY_FILES = [
    ("sectors.xlsx",          "sectors",          0, "supplementary"),
    ("stock_prices.xlsx",     "stock_prices",     0, "supplementary"),
    ("market_cap.xlsx",       "market_cap",       0, "supplementary"),
    ("financial_ratios.xlsx", "financial_ratios", 0, "supplementary"),
    ("peer_groups.xlsx",      "peer_groups",      0, "supplementary"),
]
#  SQLite Schema 
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id               TEXT PRIMARY KEY,
    company_logo     TEXT,
    company_name     TEXT NOT NULL,
    chart_link       TEXT,
    about_company    TEXT,
    website          TEXT,
    nse_profile      TEXT,
    bse_profile      TEXT,
    face_value       REAL,
    book_value       REAL,
    roce_percentage  REAL,
    roe_percentage   REAL
);

CREATE TABLE IF NOT EXISTS profitandloss (
    id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
    year TEXT NOT NULL, sales REAL, expenses REAL,
    operating_profit REAL, opm_percentage REAL, other_income REAL,
    interest REAL, depreciation REAL, profit_before_tax REAL,
    tax_percentage REAL, net_profit REAL, eps REAL, dividend_payout REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS balancesheet (
    id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
    year TEXT NOT NULL, equity_capital REAL, reserves REAL,
    borrowings REAL, other_liabilities REAL, total_liabilities REAL,
    fixed_assets REAL, cwip REAL, investments REAL,
    other_asset REAL, total_assets REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS cashflow (
    id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
    year TEXT NOT NULL, operating_activity REAL,
    investing_activity REAL, financing_activity REAL, net_cash_flow REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    compounded_sales_growth TEXT, compounded_profit_growth TEXT,
    stock_price_cagr TEXT, roe TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    Year INTEGER NOT NULL, Annual_Report TEXT
);

CREATE TABLE IF NOT EXISTS prosandcons (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    pros TEXT, cons TEXT
);

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    broad_sector TEXT, sub_sector TEXT,
    index_weight_pct REAL, market_cap_category TEXT
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    date TEXT NOT NULL, open_price REAL, high_price REAL,
    low_price REAL, close_price REAL, volume INTEGER, adjusted_close REAL
);

CREATE TABLE IF NOT EXISTS market_cap (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    year INTEGER NOT NULL, market_cap_crore REAL,
    enterprise_value_crore REAL, pe_ratio REAL, pb_ratio REAL,
    ev_ebitda REAL, dividend_yield_pct REAL
);

CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    year TEXT NOT NULL,
    net_profit_margin_pct REAL, operating_profit_margin_pct REAL,
    return_on_equity_pct REAL, debt_to_equity REAL,
    interest_coverage REAL, asset_turnover REAL,
    free_cash_flow_cr REAL, capex_cr REAL,
    earnings_per_share REAL, book_value_per_share REAL,
    dividend_payout_ratio_pct REAL, total_debt_cr REAL,
    cash_from_operations_cr REAL
);

CREATE TABLE IF NOT EXISTS peer_groups (
    id INTEGER PRIMARY KEY,
    peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL REFERENCES companies(id),
    is_benchmark TEXT
);
"""
#  Helpers 
def _get_path(filename: str, ftype: str) -> Path:
    return (RAW_DIR if ftype == "core" else SUPPORTING_DIR) / filename


def _read_excel(path: Path, header_row: int) -> pd.DataFrame:
    """Read Excel; core files have metadata row 0, so header=1."""
    df = pd.read_excel(path, header=header_row, engine="openpyxl")
    return df.dropna(how="all").dropna(axis=1, how="all")


def _strip_ttm(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Remove TTM rows — not annual data."""
    if "year" in df.columns:
        mask = df["year"].astype(str).str.upper().str.startswith("TTM")
        if mask.any():
            logger.info("Removing %d TTM rows from %s", mask.sum(), table)
            df = df[~mask]
    return df


def _normalise_ids(df: pd.DataFrame) -> pd.DataFrame:
    if "company_id" in df.columns:
        df = df.copy()
        df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def _normalise_years(df: pd.DataFrame, table: str) -> tuple[pd.DataFrame, list[dict]]:
    """Normalise year column; skip tables where year is not a financial period."""
    failures = []
    if "year" not in df.columns:
        return df, failures
    # These tables have integer years or non-period year columns — skip normalisation
    if table in ("market_cap", "peer_groups", "sectors", "stock_prices", "documents"):
        return df, failures

    new_years = []
    for val in df["year"]:
        normed = normalize_year(val)
        new_years.append(normed)
        if normed == "PARSE_ERROR":
            failures.append({
                "table": table, "company_id": "?", "field": "year",
                "raw_value": str(val), "issue": "Unparseable year format",
                "severity": "CRITICAL",
            })

    df = df.copy()
    df["year"] = new_years
    df = df[df["year"] != "PARSE_ERROR"]
    return df, failures


def _dedup(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Remove duplicate (company_id, year) pairs — keep last occurrence."""
    if table in TIME_SERIES_TABLES and "company_id" in df.columns and "year" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["company_id", "year"], keep="last")
        dropped = before - len(df)
        if dropped:
            logger.warning("Dedup: removed %d rows from %s", dropped, table)
    return df


#  Loaders 
def load_companies(path: Path, conn: sqlite3.Connection) -> dict:
    """Special loader — companies.xlsx PK is 'id', not 'company_id'."""
    t0 = time.time()
    df = _read_excel(path, 1)
    rows_in = len(df)
    df["id"] = df["id"].apply(normalize_ticker)
    df = df.drop_duplicates(subset=["id"], keep="last")
    if "company_name" in df.columns:
        df["company_name"] = df["company_name"].astype(str).str.replace("\n", " ").str.strip()
    df.to_sql("companies", conn, if_exists="replace", index=False)
    conn.commit()
    logger.info("companies: %d → %d rows loaded", rows_in, len(df))
    return {
        "table": "companies", "rows_in": rows_in, "rows_out": len(df),
        "rejected": rows_in - len(df),
        "timestamp": datetime.now().isoformat(),
        "runtime_s": round(time.time() - t0, 2),
    }


def load_table(
    path: Path, table: str, header_row: int,
    conn: sqlite3.Connection, valid_ids: set,
) -> tuple[dict, list[dict]]:
    """Generic loader for all tables except companies."""
    t0 = time.time()
    df = _read_excel(path, header_row)
    rows_in = len(df)
    all_failures: list[dict] = []

    df = _normalise_ids(df)
    df = _strip_ttm(df, table)
    df, year_fails = _normalise_years(df, table)
    all_failures.extend(year_fails)

    # FK check — reject orphan company_ids
    if "company_id" in df.columns and valid_ids:
        orphan_mask = ~df["company_id"].isin(valid_ids)
        if orphan_mask.any():
            orphans = df[orphan_mask]["company_id"].unique().tolist()
            logger.warning("%s: %d orphan rows (%s...)", table, orphan_mask.sum(), orphans[:3])
            for ticker in orphans:
                all_failures.append({
                    "table": table, "company_id": ticker,
                    "field": "company_id", "raw_value": ticker,
                    "issue": "FK integrity failure — not in companies table",
                    "severity": "CRITICAL",
                })
            df = df[~orphan_mask]

    df = _dedup(df, table)
    rows_out = len(df)

    df.to_sql(table, conn, if_exists="replace", index=False)
    conn.commit()

    logger.info(
        "%s: %d → %d rows  (rejected=%d)  %.2fs",
        table, rows_in, rows_out, rows_in - rows_out, time.time() - t0
    )
    audit = {
        "table": table, "rows_in": rows_in, "rows_out": rows_out,
        "rejected": rows_in - rows_out,
        "timestamp": datetime.now().isoformat(),
        "runtime_s": round(time.time() - t0, 2),
    }
    return audit, all_failures


#  Main orchestrator 
def run_etl() -> None:
    """Full ETL: load all 12 files, write audit CSV and validation failures CSV."""
    logger.info("=" * 60)
    logger.info("Nifty 100 ETL Pipeline — starting")
    logger.info("DB: %s", DB_PATH)
    logger.info("=" * 60)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    logger.info("Schema ready — 10 tables confirmed")

    audit_records: list[dict] = []
    all_failures: list[dict] = []

    # Load companies FIRST — all other tables FK-reference it
    companies_path = _get_path("companies.xlsx", "core")
    if not companies_path.exists():
        logger.error("companies.xlsx not found at %s — aborting", companies_path)
        conn.close()
        return
    audit_records.append(load_companies(companies_path, conn))

    # Build valid company ID set for FK checks
    valid_ids = set(r[0] for r in conn.execute("SELECT id FROM companies").fetchall())
    logger.info("Valid company IDs: %d", len(valid_ids))

    # Load remaining core files
    for filename, table, header, ftype in CORE_FILES:
        if table == "companies":
            continue
        filepath = _get_path(filename, ftype)
        if not filepath.exists():
            logger.warning("File not found — skipping: %s", filepath)
            continue
        audit, failures = load_table(filepath, table, header, conn, valid_ids)
        audit_records.append(audit)
        all_failures.extend(failures)

    # Load supplementary files
    for filename, table, header, ftype in SUPPLEMENTARY_FILES:
        filepath = _get_path(filename, ftype)
        if not filepath.exists():
            logger.warning("File not found — skipping: %s", filepath)
            continue
        audit, failures = load_table(filepath, table, header, conn, valid_ids)
        audit_records.append(audit)
        all_failures.extend(failures)

    # FK integrity check
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        logger.error("FK violations: %d rows", len(fk_violations))
    else:
        logger.info("  PRAGMA foreign_key_check → 0 violations")

    # Write output files
    with open(LOAD_AUDIT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["table","rows_in","rows_out","rejected","timestamp","runtime_s"]
        )
        writer.writeheader()
        writer.writerows(audit_records)
    logger.info("load_audit.csv written — %d tables", len(audit_records))

    if all_failures:
        with open(VALIDATION_PATH, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["table","company_id","field","raw_value","issue","severity"]
            )
            writer.writeheader()
            writer.writerows(all_failures)
        logger.info("validation_failures.csv written — %d rows", len(all_failures))

    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    logger.info("=" * 60)
    logger.info("ETL complete — companies=%d | FK violations=%d", n, len(fk_violations))
    logger.info("=" * 60)
    conn.close()


if __name__ == "__main__":
    run_etl()