from langgraph.graph import END, START, StateGraph
from typing import TypedDict

from src.agents.composer import NOT_FOUND, compose_answer
from src.agents.data_agent import run_data_agent
from src.agents.router import route_question
from src.agents.rules_agent import run_rules_agent
from src.agents.verifier import verify_answer
from src.config import TOP_K


class AdvisorState(TypedDict):
    question: str
    top_k: int
    tier: str | None
    route: str | None
    team: str | None
    trade: dict | None
    clarify_question: str | None
    clarify_count: int
    rules_result: dict | None
    data_result: dict | None
    composed: dict | None
    verdict: dict | None
    revise_count: int
    steps: list


def new_state(question, top_k=TOP_K, tier=None, clarify_count=0):
    """The state every run starts with, so every key always exists."""
    return {
        "question": question,
        "top_k": top_k,
        "tier": tier,
        "route": None,
        "team": None,
        "trade": None,
        "clarify_question": None,
        "clarify_count": clarify_count,
        "rules_result": None,
        "data_result": None,
        "composed": None,
        "verdict": None,
        "revise_count": 0,
        "steps": [],
    }


def route_node(state):
    """Work out the route, team and trade from the question."""
    result = route_question(state["question"])

    return {
        "route": result["route"],
        "team": result["team"],
        "trade": result["trade"],
        "clarify_question": result["clarify_question"],
        "steps": state["steps"] + ["route"],
    }


def rules_node(state):
    """Search the CBA"""
    question = state["question"]
    top_k = state["top_k"]
    tier = state["tier"]

    # call run_rules_agent with the question, top_k and tier from state
    rules_res = run_rules_agent(question, top_k, tier)

    # only return the state changes after the call 
    return {
        "rules_result": rules_res,
        "steps": state["steps"] + ["rules"],
    }

def data_node(state):
    """Look up the team's numbers and check the trade if there is one."""
    team = state["team"]
    trade = state["trade"]

    # no team to look up (static runs this even on pure rules questions)
    if team is None:
        return {
            "data_result": None,
            "steps": state["steps"] + ["data"],
        }

    # call run_data_agent with team and trade
    # return data_result and steps
    data_res = run_data_agent(team, trade)

    return {
        "data_result": data_res,
        "steps": state["steps"] + ["data"],
    }




def compose_node(state):
    """Write the answer from whatever the agents found."""
    question = state["question"]
    rules_result = state["rules_result"]
    data_result = state["data_result"]

    res = compose_answer(question, rules_result, data_result)

    return {
        "composed": res,
        "steps": state["steps"] + ["compose"],
    }


def verify_node(state):
    """Check the answer."""
    question = state["question"]
    composed = state["composed"]
    # call verify_answer with the question and composed
    res_verify = verify_answer(question, composed)

    return {
            "verdict": res_verify,
            "steps": state["steps"] + ["verify"],
        }


def abstain_node(state):
    """Replace the answer with a refusal."""
    # return composed as a dict with the 4 composer keys:
    # answer NOT_FOUND, abstained True, sources [], evidence ""
    # and steps (add "abstain")

    return {
    "composed": {
        "answer": NOT_FOUND,
        "abstained": True,
        "sources": [],
        "evidence": "",
        },
    "steps": state["steps"] + ["abstain"],
    }

def after_verify_static(state):
    """Static gets no retry: passed goes to the end, failed abstains."""
    if state["verdict"]["passed"]:
        return "done"
    return "abstain"


def build_static_graph():
    """Every question takes the same straight line."""
    graph = StateGraph(AdvisorState)

    # the stops  add rules, data, compose, verify and abstain the same way
    graph.add_node("route", route_node)
    graph.add_node("rules", rules_node)
    graph.add_node("data", data_node)
    graph.add_node("compose", compose_node)
    graph.add_node("verify", verify_node)
    graph.add_node("abstain", abstain_node)

    # the roads rules -> data, data -> compose, compose -> verify
    graph.add_edge(START, "route")
    graph.add_edge("route", "rules")
    graph.add_edge("rules", "data")
    graph.add_edge("data", "compose")
    graph.add_edge("compose", "verify")

    # the one fork: pick the next stop based on the verdict
    graph.add_conditional_edges("verify", after_verify_static, {"done": END, "abstain": "abstain"})

    # abstain -> END
    graph.add_edge("abstain", END)

    return graph.compile()