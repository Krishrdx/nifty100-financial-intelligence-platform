"""
test_normalise.py

unit tests for normalize_year() and normalize_ticker().

Covers every real year format found in the actual project Excel files:
  profitandloss/balancesheet : "Mar 2023","Dec 2012","Jun 2013","Sep 2011"
  cashflow                   : "Mar-23","Mar-14","Mar-13"
  financial_ratios           : "2013","2023","Dec 2012"
  Edge cases                 : "TTM","2024.5","Mar 2016 9m",None,""

Run:  pytest tests/etl/test_normalise.py -v
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.etl.normaliser import normalize_year, normalize_ticker



# normalize_year — test cases

class TestNormalizeYear:

    #  Formats from profitandloss.xlsx / balancesheet.xlsx 
    def test_mar_2023(self):         assert normalize_year("Mar 2023") == "2023-03"
    def test_mar_2024(self):         assert normalize_year("Mar 2024") == "2024-03"
    def test_mar_2011(self):         assert normalize_year("Mar 2011") == "2011-03"
    def test_mar_2012(self):         assert normalize_year("Mar 2012") == "2012-03"
    def test_dec_2012(self):         assert normalize_year("Dec 2012") == "2012-12"
    def test_dec_2022(self):         assert normalize_year("Dec 2022") == "2022-12"
    def test_dec_2023(self):         assert normalize_year("Dec 2023") == "2023-12"
    def test_jun_2013(self):         assert normalize_year("Jun 2013") == "2013-06"
    def test_jun_2015(self):         assert normalize_year("Jun 2015") == "2015-06"
    def test_sep_2011(self):         assert normalize_year("Sep 2011") == "2011-09"
    def test_sep_2024(self):         assert normalize_year("Sep 2024") == "2024-09"

    #  Hyphenated short year from cashflow.xlsx 
    def test_mar_dash_23(self):      assert normalize_year("Mar-23") == "2023-03"
    def test_mar_dash_13(self):      assert normalize_year("Mar-13") == "2013-03"
    def test_mar_dash_14(self):      assert normalize_year("Mar-14") == "2014-03"
    def test_dec_dash_22(self):      assert normalize_year("Dec-22") == "2022-12"

    #  Plain 4-digit year from financial_ratios.xlsx 
    def test_plain_2013(self):       assert normalize_year("2013") == "2013-03"
    def test_plain_2023(self):       assert normalize_year("2023") == "2023-03"
    def test_plain_2024(self):       assert normalize_year("2024") == "2024-03"

    #  Already normalised — pass-through 

    def test_already_norm_mar(self): assert normalize_year("2023-03") == "2023-03"
    def test_already_norm_dec(self): assert normalize_year("2022-12") == "2022-12"

    #  FY prefix 
    def test_fy23(self):             assert normalize_year("FY23") == "2023-03"
    def test_fy24(self):             assert normalize_year("FY24") == "2024-03"
    def test_fy_lowercase(self):     assert normalize_year("fy23") == "2023-03"
    def test_fy2023(self):          assert normalize_year("FY2023") == "2023-03"
    def test_mar_space_23(self):    assert normalize_year("Mar 23") == "2023-03"
    
    #  Edge cases : PARSE_ERROR 
    def test_ttm(self):              assert normalize_year("TTM") == "PARSE_ERROR"
    def test_decimal(self):          assert normalize_year("2024.5") == "PARSE_ERROR"
    def test_suffix_9m(self):        assert normalize_year("Mar 2016 9m") == "PARSE_ERROR"
    def test_suffix_15(self):        assert normalize_year("Mar 2023 15") == "PARSE_ERROR"
    def test_garbage(self):          assert normalize_year("garbage") == "PARSE_ERROR"
    def test_none(self):             assert normalize_year(None) == "PARSE_ERROR"
    def test_empty(self):            assert normalize_year("") == "PARSE_ERROR"
    def test_whitespace(self):       assert normalize_year("   ") == "PARSE_ERROR"


 
# normalize_ticker — 12 test cases

class TestNormalizeTicker:

    def test_already_upper(self):    assert normalize_ticker("TCS")          == "TCS"
    def test_lowercase(self):        assert normalize_ticker("tcs")          == "TCS"
    def test_mixed_case(self):       assert normalize_ticker("Tcs")          == "TCS"
    def test_leading_space(self):    assert normalize_ticker(" TCS")         == "TCS"
    def test_trailing_space(self):   assert normalize_ticker("TCS ")         == "TCS"
    def test_both_spaces(self):      assert normalize_ticker("  tcs  ")      == "TCS"
    def test_hyphen(self):           assert normalize_ticker("BAJAJ-AUTO")   == "BAJAJ-AUTO"
    def test_ampersand(self):        assert normalize_ticker("M&M")      == "M&M"
    def test_hdfcbank(self):         assert normalize_ticker("hdfcbank")     == "HDFCBANK"
    def test_spaced_ticker(self):    assert normalize_ticker(" ABBOTINDIA ") == "ABBOTINDIA"
    def test_none(self):             assert normalize_ticker(None)           == ""
    def test_empty(self):            assert normalize_ticker("")             == ""