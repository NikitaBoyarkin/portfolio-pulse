{{ config(location=var('marts_path') ~ '/' ~ this.name ~ '.parquet') }}

select
    repo,
    cast(snapshot_at as date) as snapshot_date,
    arg_max(stars, snapshot_at) as stars,
    arg_max(forks, snapshot_at) as forks
from {{ ref('stg_repo_snapshots') }}
group by 1, 2
