
-- Nifty 100 Financial Intelligence Platform — SQLite Schema
-- 10 tables · All monetary values in Indian Rupees (₹ Crore)
-- This is a REFERENCE file. Actual schema applied by src/etl/loader.py


PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id               TEXT PRIMARY KEY,   -- NSE ticker e.g. TCS
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
    id               INTEGER,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    year             TEXT NOT NULL,      -- YYYY-MM format e.g. 2023-03
    sales            REAL,              -- Net revenue (₹ Cr). Must be > 0
    expenses         REAL,
    operating_profit REAL,              -- EBITDA proxy
    opm_percentage   REAL,              -- OPM %
    other_income     REAL,
    interest         REAL,
    depreciation     REAL,
    profit_before_tax REAL,
    tax_percentage   REAL,              -- Range: 0–60%
    net_profit       REAL,              -- PAT. Can be negative
    eps              REAL,
    dividend_payout  REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS balancesheet (
    id               INTEGER,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    year             TEXT NOT NULL,
    equity_capital   REAL,
    reserves         REAL,
    borrowings       REAL,              -- 0 = debt-free
    other_liabilities REAL,
    total_liabilities REAL,            -- Must = total_assets ±1%
    fixed_assets     REAL,
    cwip             REAL,
    investments      REAL,
    other_asset      REAL,
    total_assets     REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS cashflow (
    id               INTEGER,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    year             TEXT NOT NULL,
    operating_activity  REAL,          -- CFO. Positive = healthy
    investing_activity  REAL,          -- CFI. Negative = investing
    financing_activity  REAL,          -- CFF
    net_cash_flow       REAL,          -- = CFO + CFI + CFF
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS analysis (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    compounded_sales_growth  TEXT,     -- e.g. "10 Years: 21%"
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe              TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    Year             INTEGER NOT NULL,  -- Calendar year (note capital Y)
    Annual_Report    TEXT               -- PDF URL on BSE India
);

CREATE TABLE IF NOT EXISTS prosandcons (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    pros             TEXT,
    cons             TEXT
);

CREATE TABLE IF NOT EXISTS sectors (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    broad_sector     TEXT,             -- 11 macro sectors
    sub_sector       TEXT,             -- 33 sub-sectors
    index_weight_pct REAL,
    market_cap_category TEXT
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    date             TEXT NOT NULL,    -- YYYY-MM-DD (first of month)
    open_price       REAL,
    high_price       REAL,
    low_price        REAL,
    close_price      REAL,
    volume           INTEGER,
    adjusted_close   REAL
);

CREATE TABLE IF NOT EXISTS market_cap (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    year             INTEGER NOT NULL, -- Calendar year 2019–2024
    market_cap_crore         REAL,
    enterprise_value_crore   REAL,
    pe_ratio         REAL,
    pb_ratio         REAL,
    ev_ebitda        REAL,
    dividend_yield_pct REAL
);

CREATE TABLE IF NOT EXISTS financial_ratios (
    id               INTEGER PRIMARY KEY,
    company_id       TEXT NOT NULL REFERENCES companies(id),
    year             TEXT NOT NULL,
    net_profit_margin_pct        REAL,
    operating_profit_margin_pct  REAL,
    return_on_equity_pct         REAL,
    debt_to_equity               REAL,  -- 0 = debt-free
    interest_coverage            REAL,  -- NULL if interest = 0
    asset_turnover               REAL,
    free_cash_flow_cr            REAL,  -- CFO + CFI
    capex_cr                     REAL,
    earnings_per_share           REAL,
    book_value_per_share         REAL,
    dividend_payout_ratio_pct    REAL,
    total_debt_cr                REAL,
    cash_from_operations_cr      REAL
);

CREATE TABLE IF NOT EXISTS peer_groups (
    id               INTEGER PRIMARY KEY,
    peer_group_name  TEXT NOT NULL,    -- e.g. "Private Banks"
    company_id       TEXT NOT NULL REFERENCES companies(id),
    is_benchmark     TEXT              -- "True" for the benchmark company
);