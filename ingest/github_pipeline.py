"""Load my own GitHub portfolio activity into DuckDB (or MotherDuck) with dlt.

Tables in the `raw_github` dataset:

- repos: one row per repo per run (a snapshot of stars, forks and open items)
- contributions: commits per repo over the trailing 12 months, one row per run
- contribution_calendar: contributions per day for the trailing year
- issues / pull_requests: items updated inside the lookback window, with a per-repo
  cursor in the dlt state so a daily run only adds new activity

Run:  GITHUB_TOKEN=$(gh auth token) uv run python ingest/github_pipeline.py
Env:  GITHUB_TOKEN (required), DESTINATION=duckdb|motherduck (default duckdb),
      DUCKDB_PATH (default data/github.duckdb), LOOKBACK_DAYS (default 365),
      MOTHERDUCK_TOKEN when DESTINATION=motherduck
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import dlt
import requests

GRAPHQL_URL = "https://api.github.com/graphql"
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "365"))
WINDOW_START = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
PAGE_SIZE = 50


def graphql(query: str, variables: dict) -> dict:
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"},
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def paginate(query: str, path: tuple[str, ...], variables: dict | None = None) -> Iterator[dict]:
    """Walk a connection newest-updated first; yields every node."""
    cursor = None
    while True:
        data = graphql(query, {**(variables or {}), "after": cursor})
        connection = data
        for key in path:
            connection = connection[key]
        yield from connection["nodes"]
        if not connection["pageInfo"]["hasNextPage"]:
            return
        cursor = connection["pageInfo"]["endCursor"]


def cursor_for(repo: str) -> str:
    """Per-repo cursor, so a repo added later still backfills the whole window."""
    return dlt.current.resource_state().get("cursors", {}).get(repo, WINDOW_START)


def advance_cursor(repo: str, nodes: Iterator[dict], field: str) -> Iterator[dict]:
    """Pass nodes through and move the repo's cursor to the newest timestamp seen."""
    newest = cursor_for(repo)
    for node in nodes:
        stamp = node.get(field)
        if stamp:
            newest = max(newest, stamp)
        yield node
    dlt.current.resource_state().setdefault("cursors", {})[repo] = newest


REPOS_QUERY = """
query($after: String) {
  viewer {
    login
    repositories(
      first: 100
      after: $after
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        url
        description
        createdAt
        pushedAt
        isArchived
        stargazerCount
        forkCount
        issues(states: OPEN) { totalCount }
        pullRequests(states: OPEN) { totalCount }
        primaryLanguage { name }
        licenseInfo { spdxId }
        repositoryTopics(first: 20) { nodes { topic { name } } }
      }
    }
  }
}"""


def list_repos() -> list[dict]:
    return list(paginate(REPOS_QUERY, ("viewer", "repositories")))


@dlt.resource(write_disposition="append", table_name="repos")
def repos() -> Iterator[dict]:
    snapshot_at = datetime.now(UTC).isoformat()
    for repo in list_repos():
        yield {
            "repo": repo["nameWithOwner"],
            "snapshot_at": snapshot_at,
            "url": repo["url"],
            "description": repo["description"],
            "created_at": repo["createdAt"],
            "pushed_at": repo["pushedAt"],
            "archived": repo["isArchived"],
            "stars": repo["stargazerCount"],
            "forks": repo["forkCount"],
            "open_issues": repo["issues"]["totalCount"],
            "open_pull_requests": repo["pullRequests"]["totalCount"],
            "language": (repo["primaryLanguage"] or {}).get("name"),
            "license": (repo["licenseInfo"] or {}).get("spdxId"),
            "topics": [node["topic"]["name"] for node in repo["repositoryTopics"]["nodes"]],
        }


CONTRIBUTIONS_QUERY = """
query($from90: DateTime!, $from365: DateTime!) {
  viewer {
    recent: contributionsCollection(from: $from90) {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner }
        contributions { totalCount }
      }
    }
    year: contributionsCollection(from: $from365) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner }
        contributions { totalCount }
      }
    }
  }
}"""


def contributions_data() -> dict:
    now = datetime.now(UTC)
    return graphql(
        CONTRIBUTIONS_QUERY,
        {
            "from90": (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "from365": (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )["viewer"]


@dlt.resource(write_disposition="append", table_name="contributions")
def contributions() -> Iterator[dict]:
    data = contributions_data()
    snapshot_at = datetime.now(UTC).isoformat()
    recent = {
        entry["repository"]["nameWithOwner"]: entry["contributions"]["totalCount"]
        for entry in data["recent"]["commitContributionsByRepository"]
    }
    for entry in data["year"]["commitContributionsByRepository"]:
        repo = entry["repository"]["nameWithOwner"]
        yield {
            "repo": repo,
            "snapshot_at": snapshot_at,
            "commits_12mo": entry["contributions"]["totalCount"],
            "commits_90d": recent.get(repo, 0),
        }


@dlt.resource(write_disposition="append", table_name="contribution_calendar")
def contribution_calendar() -> Iterator[dict]:
    data = contributions_data()["year"]["contributionCalendar"]
    snapshot_at = datetime.now(UTC).isoformat()
    for week in data["weeks"]:
        for day in week["contributionDays"]:
            yield {
                "login": "owner",
                "date": day["date"],
                "snapshot_at": snapshot_at,
                "contribution_count": day["contributionCount"],
            }


ISSUES_QUERY = """
query($owner: String!, $name: String!, $after: String, $pageSize: Int!) {
  repository(owner: $owner, name: $name) {
    issues(first: $pageSize, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        state
        createdAt
        updatedAt
        closedAt
        author { login }
        comments { totalCount }
      }
    }
  }
}"""


@dlt.resource(write_disposition="append", table_name="issues")
def issues() -> Iterator[dict]:
    for repo in list_repos():
        full_name = repo["nameWithOwner"]
        since = cursor_for(full_name)
        owner, name = full_name.split("/")
        nodes = paginate(
            ISSUES_QUERY,
            ("repository", "issues"),
            {"owner": owner, "name": name, "pageSize": PAGE_SIZE},
        )
        window = (
            {"number": node["number"], "title": node["title"], "state": node["state"],
             "created_at": node["createdAt"], "updated_at": node["updatedAt"],
             "closed_at": node["closedAt"], "comments": node["comments"]["totalCount"],
             "author": (node["author"] or {}).get("login"), "repo": full_name}
            for node in nodes
            if (node["updatedAt"] or "") >= since
        )
        yield from advance_cursor(full_name, window, "updated_at")


PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $after: String, $pageSize: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $pageSize, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        state
        createdAt
        updatedAt
        mergedAt
        author { login }
      }
    }
  }
}"""


@dlt.resource(write_disposition="append", table_name="pull_requests")
def pull_requests() -> Iterator[dict]:
    for repo in list_repos():
        full_name = repo["nameWithOwner"]
        since = cursor_for(full_name)
        owner, name = full_name.split("/")
        nodes = paginate(
            PULL_REQUESTS_QUERY,
            ("repository", "pullRequests"),
            {"owner": owner, "name": name, "pageSize": PAGE_SIZE},
        )
        window = (
            {"number": node["number"], "title": node["title"], "state": node["state"],
             "created_at": node["createdAt"], "updated_at": node["updatedAt"],
             "merged_at": node["mergedAt"], "author": (node["author"] or {}).get("login"),
             "repo": full_name}
            for node in nodes
            if (node["updatedAt"] or "") >= since
        )
        yield from advance_cursor(full_name, window, "updated_at")


def destination():
    if os.environ.get("DESTINATION") == "motherduck":
        return "motherduck"
    return dlt.destinations.duckdb(credentials=os.environ.get("DUCKDB_PATH", "data/github.duckdb"))


def main() -> None:
    pipeline = dlt.pipeline(
        pipeline_name="github",
        destination=destination(),
        dataset_name="raw_github",
    )
    load_info = pipeline.run(
        [repos(), contributions(), contribution_calendar(), issues(), pull_requests()]
    )
    print(load_info)


if __name__ == "__main__":
    main()
