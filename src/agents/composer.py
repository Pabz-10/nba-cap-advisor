from src.config import COMPOSER_MODEL
from src.tools.llm import get_llm

NOT_FOUND = "I couldn't find this in the CBA, so I won't guess."
DATA_LABEL = "Contracts data"


def format_chunks(chunks):
    """Turn the retrieved chunks into one block of text, each labeled with its citation and pages."""
    # build one string with each chunk's citation, pages and text
    
    chunk_blocks = []
    # loop through each chunk and build the string block form each chunk
    for chunk in chunks:
        citation = chunk["citation"]
        pages= chunk["pages"]
        text = chunk["text"]
        chunk_text = f"[{citation}] (pages {pages})\n{text}"
        chunk_blocks.append(chunk_text)

    # glues all of our blocks to one string 
    res = "\n\n".join(chunk_blocks)
    return res



def format_data(data_result):
    """Turn the data agent's numbers into labeled text the model can copy from."""
    lines = ["[" + DATA_LABEL + "]"]

    # no trade: one line with the team's current numbers
    if not data_result["trade_sides"]:
        status = data_result["status"]
        team = data_result["team"]
        payroll = data_result["payroll"]
        tier = status["tier"]
        next_line = status["next_line"]
        room = status["room"]

        # room is None over the second apron, since there's no line above it
        room_text = "none"
        if room is not None:
            room_text = f"${room:,}"

        line = f"{team}: payroll ${payroll:,}, tier {tier}, next line {next_line}, room to it {room_text}"
        lines.append(line)

    # trade: the overall result, then one line per team
    else:
        lines.append(f"Trade passes: {data_result['trade_passed']}")

        for side in data_result["trade_sides"]:
            team = side["team"]
            outgoing_players = ", ".join(side["outgoing_players"])
            incoming_players = ", ".join(side["incoming_players"])
            outgoing_total = side["outgoing_total"]
            incoming_total = side["incoming_total"]
            payroll_after = side["payroll_after"]
            tier_after = side["tier_after"]
            max_incoming = side["max_incoming"]
            passed = side["passed"]
            rule = side["rule"]

            line = f"{team}: sends {outgoing_players} (${outgoing_total:,}), takes {incoming_players} (${incoming_total:,}), lands at ${payroll_after:,} ({tier_after}), max incoming ${max_incoming:,}, passed: {passed}, rule: {rule}"
            lines.append(line)

    return "\n".join(lines)



def compose_answer(question, rules_result=None, data_result=None, feedback=None):
    """Answer using the retrieved CBA chunks and the data agent's numbers, with citations."""
    has_rules = rules_result is not None and rules_result["passed"]
    has_data = data_result is not None and data_result["error"] is None

    # nothing to work from: abstain without calling the model
    if not has_rules and not has_data:
        return {
            "answer": NOT_FOUND,
            "abstained": True,
            "sources": [],
            "evidence": "",
        }

    chunks = []
    if has_rules:
        chunks = rules_result["chunks"]

    # write the prompt: instructions + labeled chunks + team numbers + the question
    instructions = """You are answering a question about the NBA Collective Bargaining Agreement (CBA) and team salaries. Use only the CBA sections and team numbers below. Do not use outside knowledge.

Rules:
1. Every claim must cite where it came from, using the exact label in square brackets, for example [Article VII, Section 8(d)].
2. Only cite labels that appear below, or a rule named in the team numbers.
3. If the information below does not answer the question, reply with exactly: """ + NOT_FOUND + """
4. Keep the answer short and in plain language.
5. Numbers must be copied exactly from the team numbers. Never calculate your own.
6. Cite team numbers with [""" + DATA_LABEL + """]. If there is a trade, say whether it passes, and cite the rule listed for each team.

CBA sections:
"""

    data_text = ""
    if has_data:
        data_text = "\n\nTeam numbers:\n" + format_data(data_result)

    # on a retry, tell the model what was wrong with its last answer
    feedback_text = ""
    if feedback:
        feedback_text = "\n\nYour last answer was rejected. Fix this problem: " + feedback

    prompt = instructions + format_chunks(chunks) + data_text + feedback_text + "\n\nQuestion: " + question

    # send it to the composer model, fail closed if it errors
    try:
        reply = get_llm(COMPOSER_MODEL).invoke(prompt)
    except Exception:
        return {
            "answer": NOT_FOUND,
            "abstained": True,
            "sources": [],
            "evidence": "",
        }

    answer = reply.text.strip()

    # record everything the model was allowed to cite
    sources = []
    for chunk in chunks:
        sources.append(chunk["citation"])

    if has_data:
        sources.append(DATA_LABEL)
        if data_result["trade_sides"]:
            for side in data_result["trade_sides"]:
                sources.append(side["rule"])

    return {
        "answer": answer,
        "abstained": answer == NOT_FOUND,
        "sources": sources,
        "evidence": format_chunks(chunks) + data_text,
    }