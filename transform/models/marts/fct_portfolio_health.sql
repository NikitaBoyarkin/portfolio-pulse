{{ config(location=var('marts_path') ~ '/' ~ this.name ~ '.parquet') }}

with repos as (
    select
        d.repo,
        d.repo_name,
        d.layer,
        d.language,
        d.description,
        d.stars,
        d.forks,
        d.open_issues,
        d.archived,
        d.last_pushed_on,
        date_diff('day', d.last_pushed_on, current_date) as days_since_push,
        coalesce(c.commits_90d, 0) as commits_90d,
        coalesce(c.commits_12mo, 0) as commits_12mo
    from {{ ref('dim_repos') }} as d
    left join {{ ref('stg_contributions') }} as c on d.repo = c.repo
)

select
    *,
    case
        when archived then 'archived'
        when days_since_push <= 90 then 'active'
        when days_since_push <= 365 then 'quiet'
        else 'dormant'
    end as status
from repos
