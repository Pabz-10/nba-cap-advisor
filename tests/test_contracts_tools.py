import pytest

from src.tools.contracts import get_team_payroll


def test_raptors_2026_27_payroll():
    result = get_team_payroll("TOR")

    assert result["payroll"] == 201188888
    assert result["players"] == 14


def test_a_later_season_counts_only_players_still_under_contract():
    result = get_team_payroll("TOR", "2027_28")

    assert result["payroll"] == 190123915
    assert result["players"] == 10


def test_unknown_team_is_an_error_not_zero():
    with pytest.raises(ValueError):
        get_team_payroll("Raptors")


def test_unknown_season_is_an_error():
    with pytest.raises(ValueError):
        get_team_payroll("TOR", "1995_96")
