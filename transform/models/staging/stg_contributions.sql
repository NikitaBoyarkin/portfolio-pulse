with ranked as (
    select
        *,
        row_number() over (partition by repo order by snapshot_at desc) as rn
    from {{ source('raw_github', 'contributions') }}
)

select
    repo,
    commits_12mo,
    commits_90d,
    cast(snapshot_at as timestamp) as snapshot_at
from ranked
where rn = 1
