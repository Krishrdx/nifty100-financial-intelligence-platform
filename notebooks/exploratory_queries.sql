
-- Nifty 100 Financial Intelligence Platform — Sprint 1 Exploratory Queries
-- Run in VS Code SQLite Viewer : Execute SQL tab
-- Or: sqlite3 data/nifty100.db < notebooks/exploratory_queries.sql



--  Query 1: Row counts across all 12 tables
SELECT 'companies'       AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'profitandloss',  COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet',   COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow',       COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis',       COUNT(*) FROM analysis
UNION ALL SELECT 'documents',      COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons',    COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors',        COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices',   COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap',     COUNT(*) FROM market_cap
UNION ALL SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL SELECT 'peer_groups',    COUNT(*) FROM peer_groups;


--  Query 2: Year coverage per company in P&L 
SELECT
    p.company_id,
    c.company_name,
    COUNT(DISTINCT p.year)  AS year_count,
    MIN(p.year)             AS earliest_year,
    MAX(p.year)             AS latest_year
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
GROUP BY p.company_id
ORDER BY year_count ASC
LIMIT 20;


--   Query 3: Companies with less than 5 years of P&L data 
SELECT
    p.company_id,
    c.company_name,
    COUNT(*) AS year_count
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
GROUP BY p.company_id
HAVING year_count < 5
ORDER BY year_count ASC;


--  Query 4: Sector distribution 
SELECT
    broad_sector,
    COUNT(*) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;


--  Query 5: Null check on key P&L columns 
SELECT
    SUM(CASE WHEN sales IS NULL           THEN 1 ELSE 0 END) AS null_sales,
    SUM(CASE WHEN net_profit IS NULL      THEN 1 ELSE 0 END) AS null_net_profit,
    SUM(CASE WHEN eps IS NULL             THEN 1 ELSE 0 END) AS null_eps,
    SUM(CASE WHEN operating_profit IS NULL THEN 1 ELSE 0 END) AS null_op_profit,
    COUNT(*) AS total_rows
FROM profitandloss;


-- Query 6: Top 10 companies by latest-year revenue 
SELECT
    p.company_id,
    c.company_name,
    s.broad_sector,
    p.year,
    ROUND(p.sales, 0)       AS sales_cr,
    ROUND(p.net_profit, 0)  AS net_profit_cr
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
JOIN sectors s   ON p.company_id = s.company_id
WHERE p.year = (
    SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id
)
ORDER BY p.sales DESC
LIMIT 10;


--  Query 7: Debt-free companies in latest year 
SELECT
    b.company_id,
    c.company_name,
    s.broad_sector,
    b.year,
    b.borrowings
FROM balancesheet b
JOIN companies c ON b.company_id = c.id
JOIN sectors s   ON b.company_id = s.company_id
WHERE b.borrowings = 0
  AND b.year = (
      SELECT MAX(year) FROM balancesheet WHERE company_id = b.company_id
  )
ORDER BY b.company_id;


--  Query 8: Companies with positive CFO every year 
SELECT
    cf.company_id,
    c.company_name,
    COUNT(*) AS total_years,
    SUM(CASE WHEN cf.operating_activity > 0 THEN 1 ELSE 0 END) AS positive_cfo_years,
    ROUND(AVG(cf.operating_activity), 0) AS avg_cfo_cr
FROM cashflow cf
JOIN companies c ON cf.company_id = c.id
GROUP BY cf.company_id
HAVING total_years >= 5 AND positive_cfo_years = total_years
ORDER BY avg_cfo_cr DESC
LIMIT 15;


--  Query 9: Annual report coverage per company 
SELECT
    d.company_id,
    c.company_name,
    COUNT(*) AS report_count,
    MIN(d.Year) AS earliest,
    MAX(d.Year) AS latest
FROM documents d
JOIN companies c ON d.company_id = c.id
GROUP BY d.company_id
ORDER BY report_count DESC
LIMIT 20;


--  Query 10: Peer group composition 
SELECT
    peer_group_name,
    COUNT(*) AS member_count,
    GROUP_CONCAT(company_id, ', ') AS members
FROM peer_groups
GROUP BY peer_group_name
ORDER BY member_count DESC;