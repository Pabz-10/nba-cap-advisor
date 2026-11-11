from src.agents.data_agent import run_data_agent

KEYS = {"team", "payroll", "status", "trade_sides", "trade_passed", "error"}


def test_no_trade_returns_the_teams_numbers():
    result = run_data_agent("TOR")

    assert result["payroll"] == 201188888
    assert result["status"]["tier"] == "over_tax"
    assert result["trade_sides"] is None
    assert result["trade_passed"] is None
    assert result["error"] is None


def test_unknown_team_fails_closed_with_a_message():
    result = run_data_agent("Raptors")

    assert result["payroll"] is None
    assert result["error"] == "Unknown team: Raptors"


def test_trade_that_works_for_both_teams_passes():
    trade = {"TOR": ["poeltja01"], "ATL": ["daniedy01"]}

    result = run_data_agent("TOR", trade)

    assert len(result["trade_sides"]) == 2
    assert result["trade_passed"] is True
    assert result["error"] is None


def test_trade_fails_if_one_side_fails():
    # Toronto would land over the first apron, so its side fails.
    trade = {"TOR": ["poeltja01"], "CLE": ["allenja01"]}

    result = run_data_agent("TOR", trade)

    assert result["trade_sides"][0]["passed"] is False
    assert result["trade_passed"] is False


def test_player_on_the_wrong_team_fails_closed_with_a_message():
    trade = {"TOR": ["daniedy01"], "ATL": ["poeltja01"]}

    result = run_data_agent("TOR", trade)

    assert result["trade_passed"] is None
    assert result["error"] == "Dyson Daniels is on ATL, not TOR"
    assert result["payroll"] == 201188888


def test_trade_with_three_teams_fails_closed():
    trade = {"TOR": ["poeltja01"], "ATL": ["daniedy01"], "CLE": ["allenja01"]}

    result = run_data_agent("TOR", trade)

    assert result["trade_passed"] is None
    assert result["error"] is not None


def test_every_path_returns_the_same_keys():
    good_trade = {"TOR": ["poeltja01"], "ATL": ["daniedy01"]}
    bad_trade = {"TOR": ["daniedy01"], "ATL": ["poeltja01"]}

    assert set(run_data_agent("TOR")) == KEYS
    assert set(run_data_agent("Raptors")) == KEYS
    assert set(run_data_agent("TOR", good_trade)) == KEYS
    assert set(run_data_agent("TOR", bad_trade)) == KEYS
