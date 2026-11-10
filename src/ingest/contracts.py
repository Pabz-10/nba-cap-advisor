"""Clean the raw Basketball Reference salary file and save it to CSV and SQLite.

Run with: python -m src.ingest.contracts
The raw file is never changed. All cleaning happens here.
"""
import csv
import sqlite3

from src.config import (
    CONTRACTS_AS_OF,
    CONTRACTS_CSV_PATH,
    CONTRACTS_DB_PATH,
    CONTRACTS_RAW_PATH,
    PROCESSED_DIR,
)

SEASONS = ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31", "2031-32"]

# what the raw header should say, so we notice if the file ever changes
EXPECTED_HEADER = ["Rk", "Player", "Tm"] + SEASONS + ["Guaranteed", "-9999"]

# our clean column names: "2026-27" becomes "salary_2026_27"
SALARY_COLUMNS = ["salary_" + season.replace("-", "_") for season in SEASONS]
COLUMNS = ["player_id", "player", "team"] + SALARY_COLUMNS + ["guaranteed"]


def read_raw_rows(path):
    """Read the raw file into lists of values, one list per player row."""
    # the file is Windows encoded (cp1252) with Windows line endings
    with open(path, encoding="cp1252", newline="") as f:
        lines = f.read().splitlines()

    # every line is wrapped in one extra pair of double quotes, strip them
    lines = [line.strip('"') for line in lines]

    # line 1 is a junk banner, line 2 is the real header, the rest are players
    rows = list(csv.reader(lines[1:]))
    header, players = rows[0], rows[1:]
    if header != EXPECTED_HEADER:
        raise ValueError("Unexpected header: " + str(header))
    return players


def to_dollars(value):
    """'$35915403' becomes 35915403. A blank means no contract that year, so None."""
    if value == "":
        return None
    return int(value.replace("$", "").replace(",", ""))


def clean_row(values):
    """Turn one raw row into a dict with our clean column names."""
    # values[0] is the rank, which we don't need
    player, team = values[1], values[2]
    salaries = values[3:9]
    guaranteed, player_id = values[9], values[10]

    row = {"player_id": player_id, "player": player, "team": team}
    for column, value in zip(SALARY_COLUMNS, salaries):
        row[column] = to_dollars(value)
    row["guaranteed"] = to_dollars(guaranteed)
    return row


def dedupe(rows):
    """Keep one row per player: the team that owes the bigger guaranteed share.

    Six players appear on two teams (waived or traded, both teams still owe money).
    The salary columns are copied onto both rows, so counting both would double count.
    """
    kept = {}
    for row in rows:
        player_id = row["player_id"]
        if player_id not in kept:
            kept[player_id] = row
        elif (row["guaranteed"] or 0) > (kept[player_id]["guaranteed"] or 0):
            kept[player_id] = row
    return list(kept.values())


def save_csv(rows, path):
    """Write the clean rows to a CSV anyone can open."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def save_sqlite(rows, path, as_of):
    """Write the clean rows to a 'contracts' table, plus the as-of date in a 'meta' table."""
    con = sqlite3.connect(path)
    con.execute("DROP TABLE IF EXISTS contracts")
    con.execute("DROP TABLE IF EXISTS meta")
    con.execute(
        "CREATE TABLE contracts (player_id TEXT PRIMARY KEY, player TEXT, team TEXT, "
        + ", ".join(column + " INTEGER" for column in SALARY_COLUMNS)
        + ", guaranteed INTEGER)"
    )
    placeholders = ", ".join("?" for _ in COLUMNS)
    con.executemany(
        "INSERT INTO contracts VALUES (" + placeholders + ")",
        [[row[column] for column in COLUMNS] for row in rows],
    )
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('as_of', ?)", (as_of,))
    con.commit()
    con.close()


def load_contracts():
    """Raw file in, clean CSV and SQLite out. Returns the clean rows."""
    raw = read_raw_rows(CONTRACTS_RAW_PATH)
    rows = dedupe([clean_row(values) for values in raw])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    save_csv(rows, CONTRACTS_CSV_PATH)
    save_sqlite(rows, CONTRACTS_DB_PATH, CONTRACTS_AS_OF)

    print("Read " + str(len(raw)) + " raw rows, kept " + str(len(rows)) + " players")
    return rows


if __name__ == "__main__":
    load_contracts()
