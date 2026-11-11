import re

from src.config import HOME_TEAM
from src.tools.contracts import get_all_players

# TO CHANGE: add a word to one of these lists to route more questions that way.

# words that mean the question needs numbers
DATA_WORDS = ["payroll", "apron", "cap space", "tax", "room", "salary"]

# words that mean someone is proposing a trade
TRADE_WORDS = ["trade", "swap", "deal", "acquire"]

# words that point at someone without naming them
VAGUE_WORDS = ["him", "this trade", "that trade", "that player", "this player"]

# words that mean the home team
HOME_WORDS = ["we", "our", "us"]

# what people call each team, and its code in the contracts table
TEAM_NAMES = {
    "hawks": "ATL", "atlanta": "ATL",
    "celtics": "BOS", "boston": "BOS",
    "nets": "BRK", "brooklyn": "BRK",
    "hornets": "CHO", "charlotte": "CHO",
    "bulls": "CHI", "chicago": "CHI",
    "cavaliers": "CLE", "cavs": "CLE", "cleveland": "CLE",
    "mavericks": "DAL", "mavs": "DAL", "dallas": "DAL",
    "nuggets": "DEN", "denver": "DEN",
    "pistons": "DET", "detroit": "DET",
    "warriors": "GSW", "golden state": "GSW",
    "rockets": "HOU", "houston": "HOU",
    "pacers": "IND", "indiana": "IND",
    "clippers": "LAC",
    "lakers": "LAL",
    "grizzlies": "MEM", "memphis": "MEM",
    "heat": "MIA", "miami": "MIA",
    "bucks": "MIL", "milwaukee": "MIL",
    "timberwolves": "MIN", "wolves": "MIN", "minnesota": "MIN",
    "pelicans": "NOP", "new orleans": "NOP",
    "knicks": "NYK", "new york": "NYK",
    "thunder": "OKC", "oklahoma city": "OKC",
    "magic": "ORL", "orlando": "ORL",
    "76ers": "PHI", "sixers": "PHI", "philadelphia": "PHI",
    "suns": "PHO", "phoenix": "PHO",
    "blazers": "POR", "portland": "POR",
    "kings": "SAC", "sacramento": "SAC",
    "spurs": "SAS", "san antonio": "SAS",
    "raptors": "TOR", "toronto": "TOR",
    "jazz": "UTA", "utah": "UTA",
    "wizards": "WAS", "washington": "WAS",
}


def has_word(word, text):
    """True if word appears as a whole word, so 'we' doesn't match inside 'answer'."""
    return re.search(r"\b" + word + r"\b", text) is not None


def find_team(question):
    """Find a team in the question: 'Raptors' becomes 'TOR', 'we' or 'our' means the home team."""
    question = question.lower()

    # a named team wins over "we", so "can we see the Celtics payroll" means Boston
    for name, code in TEAM_NAMES.items():
        if has_word(name, question):
            return code

    for word in HOME_WORDS:
        if has_word(word, question):
            return HOME_TEAM

    return None


def find_players(question):
    """Find named players in the question, and return their IDs and teams."""
    question = question.lower()

    found = []
    for player in get_all_players():
        # full names only, since last names are shared. "Jr." and "III" are optional.
        name = player["player"].lower()
        name = name.removesuffix(" jr.").removesuffix(" iii").removesuffix(" ii")

        if name in question:
            found.append(player)

    return found


def build_trade(players):
    """Group players by team: {'TOR': ['poeltja01'], 'ATL': ['daniedy01']}."""
    # TODO: start an empty dict, loop over players, add each ID under its team
    players_dict = {}

    for player in players: 

        team = player["team"]
        if team not in players_dict:
            players_dict[team] = []
        players_dict[team].append(player["player_id"])

    return players_dict


def route_question(question):
    """Decide if a question needs rules, data, both, or a clarifying question."""
    # lowercase the question, then find the team and players
    question = question.lower()
    team = find_team(question)
    players = find_players(question)
    trade = build_trade(players)

    # TO CHANGE: the ifs below run top to bottom and the first match wins,
    # so a new rule has to go above anything it should beat.

    # check which kinds of words the question has
    is_vague = any(has_word(word, question) for word in VAGUE_WORDS)
    is_trade = any(has_word(word, question) for word in TRADE_WORDS)
    is_data = any(has_word(word, question) for word in DATA_WORDS)

    # points at someone without naming them: ask who
    if is_vague and not players:
        return {
            "route": "clarify",
            "team": team,
            "trade": None,
            "clarify_question": "Which player or trade do you mean?",
        }

    # a real trade with players from exactly 2 teams: needs rules and numbers
    if is_trade and len(trade) == 2:
        return {
            "route": "both",
            "team": team or players[0]["team"],
            "trade": trade,
            "clarify_question": None,
        }

    # a trade for a specific team, but we can't tell who's in it: ask
    if is_trade and team:
        return {
            "route": "clarify",
            "team": team,
            "trade": None,
            "clarify_question": "Which players are in the trade?",
        }

    # a numbers question about a specific team
    if is_data and team:
        return {
            "route": "data",
            "team": team,
            "trade": None,
            "clarify_question": None,
        }

    # anything else is a question about the rules
    return {
        "route": "rules",
        "team": team,
        "trade": None,
        "clarify_question": None,
    }