.PHONY: install data train eval eda app api db-up db-down test pipeline

PYTHON ?= python3
PIP ?= python3 -m pip
MODEL_BUNDLE ?= models/isolation_forest_bundle.joblib
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

install:
	$(PIP) install -e ".[dev]"

data:
	$(PYTHON) scripts/generate_dataset.py --n-rows 1000

train:
	$(PYTHON) scripts/train_model.py --data data/raw/train_logs_1000.csv

eval:
	$(PYTHON) scripts/evaluate_model.py --data data/raw/train_logs_1000.csv

eda:
	$(PYTHON) scripts/run_eda.py --data data/raw/train_logs_1000.csv

app:
	cd app && $(PYTHON) -m streamlit run streamlit_app.py

api:
	$(PYTHON) -m uvicorn qos_anomaly.api.app:app --host $(API_HOST) --port $(API_PORT) --reload

db-up:
	docker compose up -d

db-down:
	docker compose down

test:
	$(PYTHON) -m pytest -q

pipeline: data train eval
	@echo "Pipeline hoàn tất."
