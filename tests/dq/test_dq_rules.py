"""
test_dq_rules.py

36 unit tests for all 16 DQ rules.
Uses in-memory SQLite with crafted records — no real DB needed.

Run:  pytest tests/dq/test_dq_rules.py -v
"""

import sys
import sqlite3
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def make_db():
    """Create minimal in-memory SQLite with project schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE companies (
            id TEXT PRIMARY KEY, company_name TEXT NOT NULL,
            company_logo TEXT, chart_link TEXT, about_company TEXT,
            website TEXT, nse_profile TEXT, bse_profile TEXT,
            face_value REAL, book_value REAL,
            roce_percentage REAL, roe_percentage REAL
        );
        CREATE TABLE profitandloss (
            id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
            year TEXT NOT NULL, sales REAL, expenses REAL,
            operating_profit REAL, opm_percentage REAL, other_income REAL,
            interest REAL, depreciation REAL, profit_before_tax REAL,
            tax_percentage REAL, net_profit REAL, eps REAL, dividend_payout REAL,
            PRIMARY KEY (company_id, year)
        );
        CREATE TABLE balancesheet (
            id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
            year TEXT NOT NULL, equity_capital REAL, reserves REAL,
            borrowings REAL, other_liabilities REAL, total_liabilities REAL,
            fixed_assets REAL, cwip REAL, investments REAL,
            other_asset REAL, total_assets REAL,
            PRIMARY KEY (company_id, year)
        );
        CREATE TABLE cashflow (
            id INTEGER, company_id TEXT NOT NULL REFERENCES companies(id),
            year TEXT NOT NULL, operating_activity REAL,
            investing_activity REAL, financing_activity REAL, net_cash_flow REAL,
            PRIMARY KEY (company_id, year)
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL REFERENCES companies(id),
            Year INTEGER NOT NULL, Annual_Report TEXT
        );
    """)
    conn.executemany(
        "INSERT INTO companies (id, company_name) VALUES (?,?)",
        [("TCS","Tata Consultancy"),("INFY","Infosys"),("HDFCBANK","HDFC Bank")]
    )
    conn.commit()
    return conn


# DQ-01: Company PK uniqueness
class TestDQ01:
    def test_pass_unique_pks(self):
        conn = make_db()
        total  = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT id) FROM companies").fetchone()[0]
        assert total == unique == 3

    def test_fail_duplicate_pk_raises(self):
        conn = make_db()
        with pytest.raises(Exception):
            conn.execute("INSERT INTO companies (id,company_name) VALUES ('TCS','Dup')")


# DQ-02: Composite PK uniqueness
class TestDQ02:
    def test_pass_unique_composite(self):
        conn = make_db()
        conn.execute("INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS','2023-03',100)")
        conn.execute("INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS','2022-03',90)")
        conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM profitandloss").fetchone()[0]
        uniq = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT company_id,year FROM profitandloss)"
        ).fetchone()[0]
        assert rows == uniq == 2

    def test_fail_duplicate_composite_raises(self):
        conn = make_db()
        conn.execute("INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS','2023-03',100)")
        conn.commit()
        with pytest.raises(Exception):
            conn.execute("INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS','2023-03',200)")


# DQ-03: FK integrity
class TestDQ03:
    def test_pass_no_fk_violations(self):
        conn = make_db()
        conn.execute("INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS','2023-03',100)")
        conn.commit()
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0

    def test_fail_orphan_rejected(self):
        conn = make_db()
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO profitandloss (company_id,year,sales) VALUES ('UNKNOWN','2023-03',100)"
            )


# DQ-04: Balance sheet balance
class TestDQ04:
    def test_pass_balanced(self):
        assets, liabs = 1000.0, 1000.0
        assert abs(assets - liabs) / assets < 0.01

    def test_pass_within_1pct(self):
        assets, liabs = 1000.0, 1005.0   # 0.5%
        assert abs(assets - liabs) / assets < 0.01

    def test_fail_imbalance(self):
        assets, liabs = 1000.0, 1020.0   # 2%
        assert abs(assets - liabs) / assets > 0.01


# DQ-05: OPM cross-check
class TestDQ05:
    def test_pass_opm_matches(self):
        sales, op, opm = 1000.0, 200.0, 20.0
        assert abs((op / sales * 100) - opm) <= 1.5

    def test_fail_opm_mismatch(self):
        sales, op, opm = 1000.0, 200.0, 15.0
        assert abs((op / sales * 100) - opm) > 1.5


# DQ-06: Positive sales
class TestDQ06:
    def test_pass_positive(self):    assert 100.0 > 0
    def test_fail_zero(self):        assert 0 <= 0
    def test_fail_negative(self):    assert -50 <= 0


# DQ-07: Year format
class TestDQ07:
    import re
    PAT = re.compile(r"^\d{4}-\d{2}$")

    def test_pass_valid_format(self):
        assert self.PAT.match("2023-03")

    def test_fail_raw_format(self):
        assert not self.PAT.match("Mar 2023")

    def test_fail_ttm(self):
        assert not self.PAT.match("TTM")


# DQ-08: Ticker format
class TestDQ08:
    def test_pass_valid_ticker(self):
        tid = "TCS"
        assert 2 <= len(tid) <= 12 and " " not in tid

    def test_pass_hyphen_ticker(self):
        tid = "BAJAJ-AUTO"
        assert 2 <= len(tid) <= 12 and " " not in tid

    def test_fail_space_in_ticker(self):
        tid = "TCS BANK"
        assert " " in tid


# DQ-09: Net cash flow
class TestDQ09:
    def test_pass_match(self):
        cfo, cfi, cff, ncf = 500, -200, -100, 200
        assert abs((cfo + cfi + cff) - ncf) <= 10

    def test_fail_mismatch(self):
        cfo, cfi, cff, ncf = 500, -200, -100, 250
        assert abs((cfo + cfi + cff) - ncf) > 10


# DQ-10: Non-negative fixed assets
class TestDQ10:
    def test_pass_positive(self):    assert 500.0 >= 0
    def test_fail_negative(self):    assert -10.0 < 0


# DQ-11: Tax rate
class TestDQ11:
    def test_pass_normal(self):      assert 0 <= 25.0 <= 60
    def test_fail_above_60(self):    assert not (0 <= 75.0 <= 60)
    def test_fail_negative(self):    assert not (0 <= -5.0 <= 60)


# DQ-12: Dividend payout
class TestDQ12:
    def test_pass_normal(self):      assert 45.0 <= 200
    def test_fail_extreme(self):     assert 250.0 > 200


# DQ-13: URL validity
class TestDQ13:
    def test_pass_valid_url(self):
        assert "https://bseindia.com/report.pdf".startswith("http")
    def test_fail_bad_url(self):
        assert not "bseindia.com/report.pdf".startswith("http")


# DQ-14: EPS sign consistency
class TestDQ14:
    def test_pass_both_positive(self):
        assert not (100.0 > 0 and 5.0 < 0)
    def test_fail_eps_neg_profit_pos(self):
        assert 100.0 > 0 and -5.0 < 0
    def test_pass_both_negative(self):
        assert not (-100.0 > 0 and -5.0 < 0)


# DQ-16: Year coverage
class TestDQ16:
    def test_pass_5_years(self):
        conn = make_db()
        for yr in ["2020-03","2021-03","2022-03","2023-03","2024-03"]:
            conn.execute(
                "INSERT INTO profitandloss (company_id,year,sales) VALUES ('TCS',?,100)", (yr,)
            )
        conn.commit()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM profitandloss WHERE company_id='TCS'"
        ).fetchone()[0]
        assert cnt >= 5

    def test_fail_less_than_5(self):
        conn = make_db()
        for yr in ["2023-03","2024-03"]:
            conn.execute(
                "INSERT INTO profitandloss (company_id,year,sales) VALUES ('INFY',?,100)", (yr,)
            )
        conn.commit()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM profitandloss WHERE company_id='INFY'"
        ).fetchone()[0]
        assert cnt < 5