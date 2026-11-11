import pytest

from src.config import SALARY_CAP, TAX_LINE, FIRST_APRON, SECOND_APRON
from src.tools import contracts
from src.tools.contracts import check_trade_side, get_apron_status, get_player, get_team_payroll


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


def test_get_player_returns_name_team_and_salary():
    player = get_player("poeltja01")

    assert player["player"] == "Jakob Poeltl"
    assert player["team"] == "TOR"
    assert player["salary"] == 19500000


def test_unknown_player_is_an_error():
    with pytest.raises(ValueError):
        get_player("nobody01")


# Trade checks. Poeltl (TOR) earns $19.5M, Daniels (ATL) $25M, Jarrett Allen (CLE) $28M.

def test_raptors_can_swap_poeltl_for_daniels():
    # Payroll lands at $206.7M, under the first apron, so the Expanded rule allows up to $28.6M back.
    result = check_trade_side("TOR", ["poeltja01"], ["daniedy01"])

    assert result["payroll_after"] == 206688888
    assert result["tier_after"] == "over_tax"
    assert result["max_incoming"] == 28595709
    assert result["passed"] is True
    assert result["rule"] == "Article VII, Section 6(j)(1)(iv)"


def test_both_sides_of_the_same_trade_are_checked_with_the_same_function():
    raptors_side = check_trade_side("TOR", ["poeltja01"], ["daniedy01"])
    hawks_side = check_trade_side("ATL", ["daniedy01"], ["poeltja01"])

    assert raptors_side["passed"] is True
    assert hawks_side["passed"] is True


def test_raptors_cannot_take_allen_for_poeltl():
    # Payroll would land at $209.7M, over the first apron, so only 100% of outgoing ($19.5M) is allowed.
    result = check_trade_side("TOR", ["poeltja01"], ["allenja01"])

    assert result["tier_after"] == "over_first_apron"
    assert result["max_incoming"] == 19500000
    assert result["passed"] is False
    assert result["rule"] == "Article VII, Section 6(j)(3)"


def test_team_under_the_cap_can_absorb_a_player_into_cap_room():
    # Brooklyn is at $160.1M, so it has room to take Graves ($4.07M) without sending anyone back.
    result = check_trade_side("BRK", [], ["graveal01"])

    assert result["tier_after"] == "under_cap"
    assert result["passed"] is True
    assert result["rule"] == "Article VII, Section 6(j)(1)(v)"


def test_over_the_second_apron_cannot_combine_two_outgoing_salaries(monkeypatch):
    # No real team is over the second apron, so pretend the Raptors are at $230M.
    monkeypatch.setattr(contracts, "get_team_payroll", lambda team: {"payroll": 230_000_000})

    # $26.1M out for $25M back fits the 100% rule, but it combines two players.
    result = check_trade_side("TOR", ["poeltja01", "murraco01"], ["daniedy01"])

    assert result["tier_after"] == "over_second_apron"
    assert result["incoming_total"] <= result["max_incoming"]
    assert result["passed"] is False
    assert result["rule"] == "Article VII, Section 2(e)(4)"


def test_team_cannot_trade_away_another_teams_player():
    # Daniels plays for Atlanta, so Toronto can't send him out.
    with pytest.raises(ValueError):
        check_trade_side("TOR", ["daniedy01"], ["poeltja01"])


def test_trade_side_names_the_players():
    result = check_trade_side("TOR", ["poeltja01"], ["daniedy01"])

    assert result["outgoing_players"] == ["Jakob Poeltl"]
    assert result["incoming_players"] == ["Dyson Daniels"]
