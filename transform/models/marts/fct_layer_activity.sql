{{ config(location=var('marts_path') ~ '/' ~ this.name ~ '.parquet') }}

select
    d.layer,
    count(*) as repos,
    count(*) filter (where coalesce(c.commits_90d, 0) > 0) as repos_active_90d,
    sum(coalesce(c.commits_90d, 0)) as commits_90d,
    sum(coalesce(c.commits_12mo, 0)) as commits_12mo,
    sum(d.stars) as stars
from {{ ref('dim_repos') }} as d
left join {{ ref('stg_contributions') }} as c on d.repo = c.repo
group by 1
order by commits_90d desc
