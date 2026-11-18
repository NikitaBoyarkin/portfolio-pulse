# Locally everything lands in data/github.duckdb. Set TARGET=motherduck with
# MOTHERDUCK_TOKEN to write to MotherDuck instead, as the daily workflow can.
TARGET ?= local
DBT_ARGS = --project-dir transform --profiles-dir transform --target $(TARGET)

.PHONY: install ingest transform serve test lint all

install:
	uv sync --all-groups

ingest:
	DESTINATION=duckdb uv run python ingest/github_pipeline.py

transform:
	uv run dbt seed $(DBT_ARGS)
	uv run dbt build $(DBT_ARGS)

serve:
	uv run streamlit run app.py

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

all: ingest transform
