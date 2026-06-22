"""
normaliser.py

Normalisation utilities for the Nifty 100 ETL pipeline.

Two public functions:
  normalize_year(raw)   : "YYYY-MM"  string  or  "PARSE_ERROR"
  normalize_ticker(raw) : "TCS"      uppercase stripped NSE ticker

Real year formats in actual data files:
  profitandloss/balancesheet : "Mar 2023", "Dec 2012", "Jun 2013", "Sep 2011"
  cashflow                   : "Mar-23", "Mar-14", "Mar-13"
  financial_ratios           : "Mar 2023", "2013", "Dec 2012"
  Edge cases                 : "TTM", "2024.5", "Mar 2016 9m" : PARSE_ERROR
"""

import re
import logging

logger = logging.getLogger(__name__)

#  Month name : zero-padded month number 
_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

#  Compiled regex patterns 
_ALREADY_NORM  = re.compile(r"^(\d{4})-(\d{2})$")             # 2023-03
_MON_2Y        = re.compile(r"^([A-Za-z]{3,9})[- ](\d{2})$") # Mar-23 / Mar 23
_MON_4Y        = re.compile(r"^([A-Za-z]{3,9})\s+(\d{4})$")  # Mar 2023 / Dec 2012
_FY_PREFIX     = re.compile(r"^FY(\d{2,4})$", re.I)           # FY23 / FY2023
_PLAIN_4Y      = re.compile(r"^(\d{4})$")                     # 2023


_DEFAULT_MONTH = "03"   # Most Indian companies have March FY close


def normalize_year(raw) -> str:
    """
    Convert a raw year label from any source file into YYYY-MM string.

    Supported : output:
      "Mar 2023"     : "2023-03"    "Dec 2012"     : "2012-12"
      "Jun 2013"     : "2013-06"    "Sep 2011"     : "2011-09"
      "Mar-23"       : "2023-03"    "Mar-13"       : "2013-03"
      "Dec-22"       : "2022-12"    "2023"         : "2023-03"
      "FY23"         : "2023-03"    "2023-03"      : "2023-03" (pass-through)

    Returns PARSE_ERROR for:
      "TTM", "2024.5", "Mar 2016 9m", "Mar 2023 15", None, ""
    """
    if raw is None:
        return "PARSE_ERROR"

    s = str(raw).strip()
    if not s:
        return "PARSE_ERROR"

    # 1. Already normalised: 2023-03
    if _ALREADY_NORM.match(s):
        return s

    # 2. "Mar-23" or "Mar 23"  (3-letter month + 2-digit year)
    m = _MON_2Y.match(s)
    if m:
        mon = m.group(1).lower()
        if mon in _MONTH_MAP:
            n = int(m.group(2))
            yr4 = str(2000 + n) if n < 30 else str(1900 + n)
            return f"{yr4}-{_MONTH_MAP[mon]}"

    # 3. "Mar 2023" or "Dec 2012" or "Jun 2013" or "Sep 2011"
    m = _MON_4Y.match(s)
    if m:
        mon = m.group(1).lower()
        if mon in _MONTH_MAP:
            return f"{m.group(2)}-{_MONTH_MAP[mon]}"

    # 4. "FY23" or "FY2023"
    m = _FY_PREFIX.match(s)
    if m:
        yr = m.group(1)
        if len(yr) == 2:
            n = int(yr)
            yr = str(2000 + n) if n < 30 else str(1900 + n)
        return f"{yr}-{_DEFAULT_MONTH}"

    # 5. Plain 4-digit year: "2023"
    if _PLAIN_4Y.match(s):
        return f"{s}-{_DEFAULT_MONTH}"

    logger.warning("normalize_year: cannot parse %r → PARSE_ERROR", raw)
    return "PARSE_ERROR"


def normalize_ticker(raw) -> str:
    """
    Strip whitespace and uppercase the NSE ticker.

    Examples:
      "TCS"        : "TCS"         " tcs " : "TCS"
      "M&M"        : "M&M"         "BAJAJ-AUTO" : "BAJAJ-AUTO"
      None         → ""            ""      → ""
    """
    if raw is None:
        return ""
    ticker = str(raw).strip().upper()
    if not ticker:
        return ""
    if not (2 <= len(ticker) <= 12):
        logger.warning("normalize_ticker: unusual length %d for %r", len(ticker), ticker)
    return ticker