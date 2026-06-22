PYTHON = python3
SRC    = src
TESTS  = tests

.PHONY: load ratios test report dashboard api clean help

help:
	@echo ""
	@echo "  make load       Run ETL: load all 12 files into nifty100.db"
	@echo "  make ratios     Run Ratio Engine: populate financial_ratios table"
	@echo "  make test       Run full pytest suite with HTML report"
	@echo "  make report     Generate all PDF reports"
	@echo "  make dashboard  Start Streamlit on port 8501"
	@echo "  make api        Start FastAPI on port 8000"
	@echo "  make clean      Remove cache files"
	@echo ""

load:
	$(PYTHON) $(SRC)/etl/loader.py

ratios:
	$(PYTHON) $(SRC)/analytics/ratios.py

test:
	pytest $(TESTS)/ -v --html=reports/pytest_report.html --self-contained-html

report:
	$(PYTHON) $(SRC)/reports/portfolio_report.py

dashboard:
	streamlit run $(SRC)/dashboard/app.py
api:
	uvicorn $(SRC).api.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"