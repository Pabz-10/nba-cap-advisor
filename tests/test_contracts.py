import sqlite3

from src.config import CONTRACTS_DB_PATH
from src.ingest.contracts import dedupe, load_contracts, to_dollars


def query(sql):
    con = sqlite3.connect(CONTRACTS_DB_PATH)
    rows = con.execute(sql).fetchall()
    con.close()
    return rows


def test_dollar_text_becomes_a_number():
    assert to_dollars("$35915403") == 35915403


def test_blank_salary_means_no_contract():
    assert to_dollars("") is None


def test_dedupe_keeps_the_team_with_the_bigger_share():
    old_team = {"player_id": "p1", "team": "PHO", "guaranteed": 77532040}
    new_team = {"player_id": "p1", "team": "LAC", "guaranteed": 6424800}

    kept = dedupe([new_team, old_team])

    assert kept == [old_team]


def test_461_raw_rows_become_455_players():
    rows = load_contracts()

    assert len(rows) == 455


def test_every_player_appears_once():
    rows = query("SELECT player_id, COUNT(*) FROM contracts GROUP BY player_id HAVING COUNT(*) > 1")

    assert rows == []


def test_all_30_teams_are_present():
    rows = query("SELECT COUNT(DISTINCT team) FROM contracts")

    assert rows == [(30,)]


def test_lillard_is_counted_on_milwaukee_only():
    rows = query("SELECT team FROM contracts WHERE player_id = 'lillada01'")

    assert rows == [("MIL",)]


def test_raptors_2026_27_total_matches_the_raw_file():
    # No Raptors player is duplicated, so dedupe should not change their total.
    rows = query("SELECT SUM(salary_2026_27), COUNT(*) FROM contracts WHERE team = 'TOR'")

    assert rows == [(201188888, 14)]


def test_as_of_date_is_stored():
    rows = query("SELECT value FROM meta WHERE key = 'as_of'")

    assert rows == [("2026-11-05",)]
