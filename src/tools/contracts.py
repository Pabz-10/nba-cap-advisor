import sqlite3
from src.config import CONTRACTS_DB_PATH, SALARY_CAP, TAX_LINE, FIRST_APRON, SECOND_APRON, TRADE_ALLOWANCE, EXPANDED_TPE_AMOUNT
from src.ingest.contracts import SALARY_COLUMNS


def get_team_payroll(team, season="2026_27"):
    # Sum a team's salaries for one season from the contracts table.
    column = "salary_" + season

    # the column name goes straight into the SQL, so only allow real seasons
    if column not in SALARY_COLUMNS:
        raise ValueError("Unknown season: " + season)

    # sum this team's salaries for the season, count players with a contract that season,
    # and count all of the team's rows (0 means the team code doesn't exist)
    con = sqlite3.connect(CONTRACTS_DB_PATH)
    row = con.execute(
        "SELECT SUM(" + column + "), COUNT(" + column + "), COUNT(*) FROM contracts WHERE team = ?",
        (team,),
    ).fetchone()
    con.close()

    payroll, players, team_rows = row

    # fail closed: a wrong team code should be an error, never a $0 payroll
    if team_rows == 0:
        raise ValueError("Unknown team: " + team)

    return {
        "team": team,
        "season": season,
        "payroll": payroll or 0,
        "players": players,
    }

def get_player(player_id):
    """Look up one player's name, team and 2026-27 salary."""
    con = sqlite3.connect(CONTRACTS_DB_PATH)
    row = con.execute(
        "SELECT player, team, salary_2026_27 FROM contracts WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    con.close()

    # fail closed: a player we don't have is an error, never a $0 salary
    if row is None:
        raise ValueError("Unknown player: " + player_id)

    player, team, salary = row
    return {"player_id": player_id, "player": player, "team": team, "salary": salary}


def get_apron_status(payroll):
    """Say where a payroll sits against the 2026-27 cap, tax line and aprons."""
    # how far the payroll is below each line (negative means it's already over)
    room_to_cap = SALARY_CAP - payroll
    room_to_tax = TAX_LINE - payroll
    room_to_first_apron = FIRST_APRON - payroll
    room_to_second_apron = SECOND_APRON - payroll

    # pick the tier, checking from the highest line down,
    # and note the next line above it and how far away it is
    if payroll > SECOND_APRON:
        tier = "over_second_apron"
        next_line = None
        room = None

    elif payroll > FIRST_APRON:
        tier = "over_first_apron"
        next_line = "second_apron"
        room = room_to_second_apron

    elif payroll > TAX_LINE:
        tier = "over_tax"
        next_line = "first_apron"
        room = room_to_first_apron

    elif payroll > SALARY_CAP:
        tier = "over_cap"
        next_line = "tax_line"
        room = room_to_tax

    else:
        tier = "under_cap"
        next_line = "salary_cap"
        room = room_to_cap

    return {
        "payroll": payroll,
        "tier": tier,
        "next_line": next_line,
        "room": room,
    }

def check_trade_side(team, outgoing_ids, incoming_ids):
    """Check one team's side of a trade: new payroll, new apron tier, and salary matching."""
    # get the team's payroll before the trade
    payroll_before = get_team_payroll(team)["payroll"]

    # look up outgoing and incoming players, and add up each side's salaries
    # a team can only trade away its own players (the other side's check covers incoming players)
    outgoing_total = 0
    for player_id in outgoing_ids:
        player = get_player(player_id)
        if player["team"] != team:
            raise ValueError(player["player"] + " is on " + player["team"] + ", not " + team)
        outgoing_total = outgoing_total + player["salary"]

    incoming_total = 0
    for player_id in incoming_ids:
        incoming_total = incoming_total + get_player(player_id)["salary"]

    # work out the payroll after the trade and its apron status
    payroll_after = payroll_before - outgoing_total + incoming_total
    tier_after = get_apron_status(payroll_after)["tier"]

    # work out the most salary this team may take back, based on where it lands after the trade
    if tier_after == "under_cap":
        # still under the cap: anything that fits in cap room, plus the allowance
        rule = "Article VII, Section 6(j)(1)(v)"
        max_incoming = SALARY_CAP - (payroll_before - outgoing_total) + TRADE_ALLOWANCE

    elif tier_after == "over_cap" or tier_after == "over_tax":
        # over the cap but at or under the first apron: Expanded Traded Player Exception
        rule = "Article VII, Section 6(j)(1)(iv)"
        max_incoming = max(
            min(2 * outgoing_total + TRADE_ALLOWANCE, outgoing_total + EXPANDED_TPE_AMOUNT),
            int(1.25 * outgoing_total) + TRADE_ALLOWANCE,
        )

    else:
        # over the first or second apron: only 100% of outgoing, no allowance
        rule = "Article VII, Section 6(j)(3)"
        max_incoming = outgoing_total

    # decide if it passes: incoming within the limit,
    # and over the second apron a team can't combine two or more outgoing salaries
    passed = incoming_total <= max_incoming
    if tier_after == "over_second_apron" and len(outgoing_ids) > 1:
        passed = False
        rule = "Article VII, Section 2(e)(4)"

    return {
        "team": team,
        "payroll_before": payroll_before,
        "payroll_after": payroll_after,
        "tier_after": tier_after,
        "outgoing_total": outgoing_total,
        "incoming_total": incoming_total,
        "max_incoming": max_incoming,
        "passed": passed,
        "rule": rule,
    }