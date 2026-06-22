Day 02 – Excel Loader & Normaliser

Implemented normalize_year() and normalize_ticker().

normalize_year converts multiple formats:
Mar 2023 → 2023-03
Dec 2022 → 2022-12
Mar-23 → 2023-03
FY23 → 2023-03

Invalid values return PARSE_ERROR:
TTM
2024.5
Mar 2016 9m

normalize_ticker standardizes company IDs by removing spaces and converting to uppercase.

Created 45 unit tests covering valid, invalid and edge cases.

Results:
45 passed
0 failed

ETL pipeline successfully loaded all source files and generated:
load_audit.csv
validation_failures.csv

Foreign key violations in database:
0