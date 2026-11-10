import sqlite3
from src.config import CONTRACTS_DB_PATH
from src.ingest.contracts import SALARY_COLUMNS


def get_team_payroll(team, season="2026_27"):
    #Sum a team's salaries for one season from the contracts table.
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