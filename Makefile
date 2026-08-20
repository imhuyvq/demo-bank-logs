.PHONY: install data train eval app db-up db-down test pipeline

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e ".[dev]"

data:
	$(PYTHON) scripts/generate_dataset.py --n-rows 1000

train:
	$(PYTHON) scripts/train_model.py --data data/raw/train_logs_1000.csv

eval:
	$(PYTHON) scripts/evaluate_model.py --data data/raw/train_logs_1000.csv

app:
	cd app && $(PYTHON) -m streamlit run streamlit_app.py

db-up:
	docker compose up -d

db-down:
	docker compose down

test:
	$(PYTHON) -m pytest -q

pipeline: data train eval
