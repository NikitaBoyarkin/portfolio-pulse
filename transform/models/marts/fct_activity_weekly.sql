{{ config(location=var('marts_path') ~ '/' ~ this.name ~ '.parquet') }}

select
    cast(date_trunc('week', contribution_date) as date) as week_start,
    sum(contribution_count) as contributions
from {{ ref('stg_contribution_calendar') }}
group by 1
order by 1
