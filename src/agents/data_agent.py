from src.tools.contracts import get_team_payroll, get_apron_status, check_trade_side


def run_data_agent(team, trade=None):
    """Look up a team's cap numbers, and check both sides of a trade if one is given."""
    # TODO: get the team's payroll and apron status (fail closed if anything errors)
    try:
        res_payroll = get_team_payroll(team)
        res_apron = get_apron_status(res_payroll["payroll"])
    except ValueError as e:
        return {
            "team": team,
            "payroll": None,
            "trade_sides": None,
            "trade_passed": None,
            "status": None,
            "error": str(e)
        }

    # TODO: if there's no trade, return the numbers
        # if there's no trade, return the numbers
    if trade == None:
        return {
            "team": team,
            "payroll": res_payroll["payroll"],
            "status": res_apron,
            "trade_sides": None,
            "trade_passed": None,
            "error": None,
        }

    # TODO: check each side of the trade with check_trade_side (fail closed if anything errors)
    try:
        team_a, team_b = trade.keys()

        trade_side_a = check_trade_side(team_a, trade[team_a], trade[team_b])
        trade_side_b = check_trade_side(team_b, trade[team_b], trade[team_a])

    except ValueError as e:
        return {
            "team": team,
            "payroll": res_payroll["payroll"],
            "status": res_apron,
            "trade_sides": None,
            "trade_passed": None,
            "error": str(e),
        }

    # return the numbers, both sides, and whether the whole trade works (both sides pass)
    return {
            "team": team,
            "payroll": res_payroll["payroll"],
            "status": res_apron,
            "trade_sides": [trade_side_a, trade_side_b],
            "trade_passed": trade_side_a["passed"] and trade_side_b["passed"],
            "error": None,
            }