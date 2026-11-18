{{ config(location=var('marts_path') ~ '/' ~ this.name ~ '.parquet') }}

select
    r.repo,
    split_part(r.repo, '/', 2) as repo_name,
    r.url,
    r.description,
    coalesce(l.layer, 'other') as layer,
    r.language,
    r.license,
    cast(r.created_at as date) as created_on,
    cast(r.pushed_at as date) as last_pushed_on,
    r.archived,
    r.stars,
    r.forks,
    r.open_issues,
    r.open_pull_requests
from {{ ref('stg_repos') }} as r
left join {{ ref('repo_layers') }} as l on r.repo = l.repo
