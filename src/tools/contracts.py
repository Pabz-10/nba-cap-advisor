import sqlite3
from src.config import CONTRACTS_DB_PATH, SALARY_CAP, TAX_LINE, FIRST_APRON, SECOND_APRON
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