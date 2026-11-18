with ranked as (
    select
        *,
        row_number() over (partition by "date" order by snapshot_at desc) as rn
    from {{ source('raw_github', 'contribution_calendar') }}
)

select
    cast("date" as date) as contribution_date,
    contribution_count
from ranked
where rn = 1
