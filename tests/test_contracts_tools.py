import pytest

from src.config import SALARY_CAP, TAX_LINE, FIRST_APRON, SECOND_APRON
from src.tools.contracts import get_apron_status, get_team_payroll


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


def test_raptors_are_over_the_tax_and_below_the_first_apron():
    status = get_apron_status(201188888)

    assert status["tier"] == "over_tax"
    assert status["next_line"] == "first_apron"
    assert status["room"] == 7826112


def test_under_the_cap():
    status = get_apron_status(150_000_000)

    assert status["tier"] == "under_cap"
    assert status["next_line"] == "salary_cap"
    assert status["room"] == SALARY_CAP - 150_000_000


def test_over_the_cap_but_under_the_tax():
    status = get_apron_status(180_000_000)

    assert status["tier"] == "over_cap"
    assert status["next_line"] == "tax_line"


def test_over_the_first_apron():
    status = get_apron_status(215_000_000)

    assert status["tier"] == "over_first_apron"
    assert status["next_line"] == "second_apron"


def test_over_the_second_apron_has_no_next_line():
    status = get_apron_status(230_000_000)

    assert status["tier"] == "over_second_apron"
    assert status["next_line"] is None
    assert status["room"] is None


def test_exactly_on_a_line_counts_as_under_it():
    status = get_apron_status(FIRST_APRON)

    assert status["tier"] == "over_tax"
    assert status["room"] == 0


def test_raptors_payroll_and_status_together():
    payroll = get_team_payroll("TOR")["payroll"]
    status = get_apron_status(payroll)

    assert status["tier"] == "over_tax"
