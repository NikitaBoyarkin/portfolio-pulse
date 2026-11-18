select
    repo,
    cast(snapshot_at as timestamp) as snapshot_at,
    stars,
    forks,
    open_issues,
    open_pull_requests
from {{ source('raw_github', 'repos') }}
