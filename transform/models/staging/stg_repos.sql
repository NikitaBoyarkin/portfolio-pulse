with ranked as (
    select
        *,
        row_number() over (partition by repo order by snapshot_at desc) as rn
    from {{ source('raw_github', 'repos') }}
)

select
    repo,
    url,
    description,
    cast(created_at as timestamp) as created_at,
    cast(pushed_at as timestamp) as pushed_at,
    archived,
    stars,
    forks,
    open_issues,
    open_pull_requests,
    language,
    license,
    cast(snapshot_at as timestamp) as snapshot_at
from ranked
where rn = 1
