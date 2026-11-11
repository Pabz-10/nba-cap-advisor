from src.agents.data_agent import run_data_agent
from src.agents.router import TEAM_NAMES, build_trade, find_players, find_team, route_question
from src.tools.contracts import get_all_players, get_team_payroll


def ids(players):
    return sorted(player["player_id"] for player in players)


def test_nickname_becomes_team_code():
    assert find_team("What is the Raptors payroll?") == "TOR"


def test_city_becomes_team_code():
    assert find_team("how much cap space does Boston have") == "BOS"


def test_two_word_city():
    assert find_team("Is New York over the apron?") == "NYK"


def test_we_means_the_home_team():
    assert find_team("are we over the tax?") == "TOR"


def test_our_means_the_home_team():
    assert find_team("what is our payroll") == "TOR"


def test_a_named_team_wins_over_we():
    assert find_team("can we see the Celtics payroll?") == "BOS"


def test_we_inside_another_word_is_not_the_home_team():
    assert find_team("what were the answers?") is None


def test_team_name_inside_another_word_is_not_a_team():
    assert find_team("cabinets of wheat") is None


def test_no_team_gives_none():
    assert find_team("How long after signing can a rookie be traded?") is None


def test_every_team_code_is_real():
    # get_team_payroll raises an error if a code doesn't exist
    for code in TEAM_NAMES.values():
        get_team_payroll(code)


def test_all_30_teams_can_be_named():
    assert len(set(TEAM_NAMES.values())) == 30


def test_finds_both_players_in_a_trade():
    players = find_players("Can we trade Jakob Poeltl for Dyson Daniels?")

    assert ids(players) == ["daniedy01", "poeltja01"]


def test_found_players_come_with_their_team():
    players = find_players("jakob poeltl")

    assert players == [{"player_id": "poeltja01", "player": "Jakob Poeltl", "team": "TOR"}]


def test_last_name_alone_is_not_enough():
    assert find_players("trade Allen for Poeltl") == []


def test_shared_last_name_finds_the_right_player():
    players = find_players("What about Jarrett Allen?")

    assert ids(players) == ["allenja01"]


def test_repaired_name_can_be_found():
    assert ids(find_players("Nikola Jokic")) == ["jokicni01"]


def test_jr_is_optional():
    assert ids(find_players("Jaren Jackson")) == ["jacksja02"]
    assert ids(find_players("Jaren Jackson Jr.")) == ["jacksja02"]


def test_no_players_gives_empty_list():
    assert find_players("Can we trade him?") == []


def test_every_player_can_be_found_by_their_own_name():
    for player in get_all_players():
        assert player in find_players(player["player"])


def test_build_trade_groups_players_by_team():
    players = find_players("Jakob Poeltl for Dyson Daniels")

    assert build_trade(players) == {"TOR": ["poeltja01"], "ATL": ["daniedy01"]}


def test_build_trade_keeps_two_players_from_one_team_together():
    players = [
        {"player_id": "a", "player": "A", "team": "TOR"},
        {"player_id": "b", "player": "B", "team": "TOR"},
    ]

    assert build_trade(players) == {"TOR": ["a", "b"]}


def test_named_trade_goes_to_both():
    result = route_question("Can we trade Jakob Poeltl for Dyson Daniels?")

    assert result["route"] == "both"
    assert result["trade"] == {"TOR": ["poeltja01"], "ATL": ["daniedy01"]}


def test_vague_player_asks_who():
    result = route_question("can we trade him?")

    assert result["route"] == "clarify"
    assert result["clarify_question"] == "Which player or trade do you mean?"


def test_trade_without_players_asks_which_players():
    result = route_question("can we make a trade?")

    assert result["route"] == "clarify"
    assert result["clarify_question"] == "Which players are in the trade?"


def test_team_numbers_question_goes_to_data():
    result = route_question("What is the Raptors payroll?")

    assert result["route"] == "data"
    assert result["team"] == "TOR"


def test_general_trade_rule_goes_to_rules_not_clarify():
    result = route_question("Can a team above the second apron aggregate player salaries in a trade?")

    assert result["route"] == "rules"


def test_plain_rules_question_goes_to_rules():
    assert route_question("How long after signing can a draft rookie be traded?")["route"] == "rules"


def test_every_route_returns_the_same_keys():
    questions = [
        "Can we trade Jakob Poeltl for Dyson Daniels?",
        "can we trade him?",
        "What is the Raptors payroll?",
        "How long after signing can a draft rookie be traded?",
    ]
    for question in questions:
        assert set(route_question(question)) == {"route", "team", "trade", "clarify_question"}


def test_trade_with_no_team_mentioned_still_works_in_the_data_agent():
    result = route_question("Trade Jakob Poeltl for Dyson Daniels")
    data = run_data_agent(result["team"], result["trade"])

    assert data["error"] is None
    assert data["trade_passed"] is True
