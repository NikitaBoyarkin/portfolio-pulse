import csv
from pathlib import Path

SEED = Path(__file__).parents[1] / "transform" / "seeds" / "repo_layers.csv"
LAYERS = {"data", "web", "learning", "vault", "other"}


def rows() -> list[dict]:
    with SEED.open() as handle:
        return list(csv.DictReader(handle))


def test_every_repo_has_one_valid_layer():
    entries = rows()
    assert entries, "seed is empty"
    repos = [entry["repo"] for entry in entries]
    assert len(repos) == len(set(repos)), "duplicate repo in seed"
    unknown = {entry["layer"] for entry in entries} - LAYERS
    assert not unknown, f"unknown layers: {unknown}"


def test_repos_are_owner_qualified():
    assert all(entry["repo"].count("/") == 1 for entry in rows())
