"""
validator.py

16 DQ rules for the Nifty 100 ETL pipeline.

Run AFTER loader.py has populated nifty100.db.
Run:  python src/etl/validator.py

DQ Rules Summary:
  DQ-01  CRITICAL  Company PK uniqueness
  DQ-02  CRITICAL  (company_id, year) composite PK uniqueness
  DQ-03  CRITICAL  FK integrity — PRAGMA foreign_key_check
  DQ-04  WARNING   Balance sheet |assets − liabilities| / assets < 1%
  DQ-05  WARNING   OPM cross-check |stored − computed| < 1.5%
  DQ-06  WARNING   Positive sales (sales > 0)
  DQ-07  CRITICAL  Year format — all years match YYYY-MM
  DQ-08  CRITICAL  Ticker format — length 2–12, no spaces
  DQ-09  WARNING   Net cash flow matches CFO + CFI + CFF ±10 Cr
  DQ-10  WARNING   Non-negative fixed assets
  DQ-11  WARNING   Tax rate 0–60%
  DQ-12  WARNING   Dividend payout ≤ 200%
  DQ-13  WARNING   Annual report URL starts with http
  DQ-14  WARNING   EPS sign consistent with net_profit sign
  DQ-15  INFO      Balance sheet strict balance (informational)
  DQ-16  WARNING   Year coverage ≥ 5 years P&L per company
"""

import os
import re
import sys
import sqlite3
import csv
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("etl.validator")

DB_PATH    = ROOT / os.getenv("DB_PATH",    "data/nifty100.db")
OUTPUT_DIR = ROOT / os.getenv("OUTPUT_DIR", "output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DQ_OUT     = OUTPUT_DIR / "dq_validation_report.csv"

_failures: list[dict] = []


def _fail(rule, table, company_id, field, value, issue, severity):
    _failures.append({
        "rule": rule, "table": table, "company_id": company_id,
        "field": field, "raw_value": str(value),
        "issue": issue, "severity": severity,
    })


def run_all_rules(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    logger.info("Running 16 DQ rules against nifty100.db ...")
    logger.info("─" * 50)

    # DQ-01: Company PK uniqueness
    total  = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    unique = c.execute("SELECT COUNT(DISTINCT id) FROM companies").fetchone()[0]
    if total != unique:
        _fail("DQ-01","companies","ALL","id", total - unique,
              f"Duplicate company PKs: {total - unique} found", "CRITICAL")
        logger.error("DQ-01 FAIL: %d duplicate company PKs", total - unique)
    else:
        logger.info("DQ-01 PASS  companies PK unique (%d rows)", total)

    # DQ-02: (company_id, year) composite PK uniqueness
    for tbl in ["profitandloss", "balancesheet", "cashflow", "financial_ratios"]:
        rows = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        uniq = c.execute(
            f"SELECT COUNT(*) FROM (SELECT DISTINCT company_id, year FROM {tbl})"
        ).fetchone()[0]
        if rows != uniq:
            _fail("DQ-02", tbl, "ALL", "company_id+year", rows - uniq,
                  f"{rows - uniq} duplicate (company_id,year) pairs", "CRITICAL")
            logger.error("DQ-02 FAIL  %s: %d duplicates", tbl, rows - uniq)
        else:
            logger.info("DQ-02 PASS  %s composite PK unique", tbl)

    # DQ-03: FK integrity
    fk_rows = c.execute("PRAGMA foreign_key_check").fetchall()
    if fk_rows:
        for row in fk_rows:
            _fail("DQ-03", row[0], "?", "company_id", row[2], "FK violation", "CRITICAL")
        logger.error("DQ-03 FAIL  %d FK violations", len(fk_rows))
    else:
        logger.info("DQ-03 PASS  FK integrity — 0 violations")

    # DQ-04: Balance sheet balance
    rows = c.execute(
        "SELECT company_id, year, total_assets, total_liabilities "
        "FROM balancesheet WHERE total_assets > 0"
    ).fetchall()
    dq04 = 0
    for cid, yr, assets, liabs in rows:
        if liabs is None:
            continue
        if abs(assets - liabs) / assets > 0.01:
            _fail("DQ-04", "balancesheet", cid, "total_assets vs total_liabilities",
                  f"assets={assets:.0f} liabs={liabs:.0f}",
                  "BS imbalance >1%", "WARNING")
            dq04 += 1
    logger.info("DQ-04  %d rows checked  %d imbalances >1%%", len(rows), dq04)

    # DQ-05: OPM cross-check
    rows = c.execute(
        "SELECT company_id, year, sales, operating_profit, opm_percentage "
        "FROM profitandloss WHERE sales > 0 AND opm_percentage IS NOT NULL"
    ).fetchall()
    dq05 = 0
    for cid, yr, sales, op, opm in rows:
        computed = (op / sales) * 100
        if abs(computed - opm) > 1.5:
            _fail("DQ-05", "profitandloss", cid, "opm_percentage",
                  f"stored={opm:.1f} computed={computed:.1f}",
                  "OPM mismatch >1.5%", "WARNING")
            dq05 += 1
    logger.info("DQ-05  %d rows checked  %d OPM mismatches", len(rows), dq05)

    # DQ-06: Positive sales
    rows = c.execute(
        "SELECT company_id, year, sales FROM profitandloss "
        "WHERE sales IS NOT NULL AND sales <= 0"
    ).fetchall()
    for cid, yr, sales in rows:
        _fail("DQ-06", "profitandloss", cid, "sales", sales, "Sales <= 0", "WARNING")
    logger.info("DQ-06  %d zero/negative sales rows", len(rows))

    # DQ-07: Year format
    pat = re.compile(r"^\d{4}-\d{2}$")
    dq07 = 0
    for tbl in ["profitandloss", "balancesheet", "cashflow"]:
        for cid, yr in c.execute(f"SELECT DISTINCT company_id, year FROM {tbl}").fetchall():
            if not pat.match(str(yr)):
                _fail("DQ-07", tbl, cid, "year", yr, "Year not YYYY-MM", "CRITICAL")
                dq07 += 1
    logger.info("DQ-07  year format check complete — %d bad rows", dq07)

    # DQ-08: Ticker format
    tickers = c.execute("SELECT id FROM companies").fetchall()
    dq08 = 0
    for (tid,) in tickers:
        if not (2 <= len(str(tid)) <= 12) or " " in str(tid):
            _fail("DQ-08", "companies", tid, "id", tid, "Ticker format invalid", "CRITICAL")
            dq08 += 1
    logger.info("DQ-08  %d tickers checked  %d invalid", len(tickers), dq08)

    # DQ-09: Net cash flow vs components
    rows = c.execute(
        "SELECT company_id, year, operating_activity, investing_activity, "
        "financing_activity, net_cash_flow FROM cashflow WHERE net_cash_flow IS NOT NULL"
    ).fetchall()
    dq09 = 0
    for cid, yr, cfo, cfi, cff, ncf in rows:
        computed = (cfo or 0) + (cfi or 0) + (cff or 0)
        if abs(computed - ncf) > 10:
            _fail("DQ-09", "cashflow", cid, "net_cash_flow",
                  f"stored={ncf:.0f} computed={computed:.0f}",
                  "Net cash mismatch >10 Cr", "WARNING")
            dq09 += 1
    logger.info("DQ-09  %d rows  %d mismatches >10 Cr", len(rows), dq09)

    # DQ-10: Non-negative fixed assets
    rows = c.execute(
        "SELECT company_id, year, fixed_assets FROM balancesheet WHERE fixed_assets < 0"
    ).fetchall()
    for cid, yr, fa in rows:
        _fail("DQ-10", "balancesheet", cid, "fixed_assets", fa,
              "Negative fixed_assets", "WARNING")
    logger.info("DQ-10  %d negative fixed_assets rows", len(rows))

    # DQ-11: Tax rate 0–60%
    rows = c.execute(
        "SELECT company_id, year, tax_percentage FROM profitandloss "
        "WHERE tax_percentage IS NOT NULL"
    ).fetchall()
    dq11 = 0
    for cid, yr, tx in rows:
        if not (0 <= tx <= 60):
            _fail("DQ-11", "profitandloss", cid, "tax_percentage", tx,
                  "Tax rate outside 0–60%", "WARNING")
            dq11 += 1
    logger.info("DQ-11  %d rows  %d out-of-range tax rates", len(rows), dq11)

    # DQ-12: Dividend payout cap
    rows = c.execute(
        "SELECT company_id, year, dividend_payout FROM profitandloss "
        "WHERE dividend_payout > 200"
    ).fetchall()
    for cid, yr, dp in rows:
        _fail("DQ-12", "profitandloss", cid, "dividend_payout", dp,
              "Dividend payout >200%", "WARNING")
    logger.info("DQ-12  %d extreme payout rows", len(rows))

    # DQ-13: URL validity (format check)
    rows = c.execute(
        "SELECT company_id, Year, Annual_Report FROM documents "
        "WHERE Annual_Report IS NOT NULL"
    ).fetchall()
    dq13 = 0
    for cid, yr, url in rows:
        if not str(url).startswith("http"):
            _fail("DQ-13", "documents", cid, "Annual_Report", url,
                  "URL does not start with http", "WARNING")
            dq13 += 1
    logger.info("DQ-13  %d docs checked  %d bad URLs", len(rows), dq13)

    # DQ-14: EPS sign consistency
    rows = c.execute(
        "SELECT company_id, year, net_profit, eps FROM profitandloss "
        "WHERE eps IS NOT NULL AND net_profit IS NOT NULL"
    ).fetchall()
    dq14 = 0
    for cid, yr, np_, eps in rows:
        if np_ > 0 and eps < 0:
            _fail("DQ-14", "profitandloss", cid, "eps", eps,
                  "EPS negative but net_profit positive", "WARNING")
            dq14 += 1
    logger.info("DQ-14  %d EPS sign mismatches", dq14)

    # DQ-15: Strict BS balance (informational)
    n = c.execute(
        "SELECT COUNT(*) FROM balancesheet WHERE ABS(total_assets - total_liabilities) > 1"
    ).fetchone()[0]
    logger.info("DQ-15 INFO  %d rows where |assets−liabilities| > 1 Cr", n)

    # DQ-16: Coverage — ≥5 years P&L per company
    rows = c.execute(
        "SELECT company_id, COUNT(*) AS yr_count FROM profitandloss "
        "GROUP BY company_id HAVING yr_count < 5"
    ).fetchall()
    for cid, cnt in rows:
        _fail("DQ-16", "profitandloss", cid, "year_count", cnt,
              f"Only {cnt} P&L years — CAGR needs ≥5", "WARNING")
    logger.info("DQ-16  %d companies with <5yr P&L data", len(rows))


def main() -> None:
    if not DB_PATH.exists():
        logger.error("DB not found at %s — run loader.py first", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    run_all_rules(conn)
    conn.close()

    critical = sum(1 for f in _failures if f["severity"] == "CRITICAL")
    warning  = sum(1 for f in _failures if f["severity"] == "WARNING")

    with open(DQ_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["rule","table","company_id","field","raw_value","issue","severity"]
        )
        writer.writeheader()
        writer.writerows(_failures)

    logger.info("─" * 50)
    logger.info("DQ Results:  CRITICAL=%d  WARNING=%d  Total=%d",
                critical, warning, len(_failures))
    logger.info("Report → %s", DQ_OUT)

    if critical > 0:
        logger.error("  CRITICAL failures — resolve before Sprint 2!")
    else:
        logger.info("  No CRITICAL failures — ready for Sprint 2")


if __name__ == "__main__":
    main()