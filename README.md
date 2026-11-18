# portfolio-pulse

A zero-dollar data stack over my own GitHub portfolio: **dlt → DuckDB → dbt → GitHub Actions →
Streamlit**. No paid accounts, no servers, no secrets in the dashboard.

Inspired by [zero-dollar-data-stack](https://github.com/lelouvincx/zero-dollar-data-stack), which
tracks OSS tools someone else maintains. This one tracks my own repos — the questions are different,
so the metrics are too: not "does the maintainer answer", but "is this project still alive".

| Layer | Tool | Where |
| --- | --- | --- |
| Ingestion | [dlt](https://dlthub.com/) + GitHub GraphQL | `ingest/github_pipeline.py` |
| Storage | [DuckDB](https://duckdb.org/) — one file, `data/github.duckdb` | local |
| Transformation | [dbt Core](https://github.com/dbt-labs/dbt) (`dbt-duckdb`) | `transform/` |
| Orchestration | GitHub Actions, daily at 03:00 UTC | `.github/workflows/refresh.yml` |
| BI | [Streamlit](https://streamlit.io/) | `app.py` |

## Run it

```sh
uv sync --all-groups
GITHUB_TOKEN=$(gh auth token) make ingest   # ~1-2 minutes, 55 public repos
make transform                              # dbt seed + build + tests
make serve                                  # http://localhost:8501
make test
```

Everything lands in `data/github.duckdb`. The marts are published as parquet in `data/marts/`.

## Metrics

Defined once in dbt, `transform/models/marts/`:

- **Freshness** — days since the last push, per repo.
- **Status** — `active` (pushed within 90 days), `quiet` (within a year), `dormant` (older), `archived`.
- **Commits 90d / 12mo** — per repo, from `commitContributionsByRepository` over two windows.
- **Activity by week** — contributions per week for the trailing year.
- **Where the time goes** — commits per layer (`data`, `web`, `learning`, `vault`), joined from the
  `repo_layers` seed.
- **Stars** — snapshot per run, so history starts the day the pipeline first ran.

## Known limits

- **Public repos only.** The dashboard is public, so ingest filters `privacy: PUBLIC`; a private repo
  never reaches the parquet files. The contribution calendar still counts private activity as an
  unattributed daily total — the same number GitHub shows on the profile.
- **365-day window.** Contribution and issue/PR lookbacks stop at a year.
- **Stars are snapshots**, not backfilled history.
- **Issues and PRs are near-empty on this domain** (a solo portfolio gets few). They are staged for
  completeness; the load-bearing metrics are freshness and activity.
- **Data in git.** The daily workflow commits `data/marts/*.parquet` (~100 KB) back to `main`: one
  commit a day, the price of having no database account. Move to a release asset or MotherDuck if the
  history noise starts to hurt.
- `dbt` on `PATH` may be a different distribution; always run it through `uv run dbt` (dbt-core from
  `dbt-duckdb`), never the bare binary.
