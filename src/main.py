"""Ask the NBA Cap and Trade Advisor a question from the command line.

Run with: python -m src.main "What is the Raptors payroll?" --mode dynamic
"""
import argparse

from src.config import TOP_K
from src.graph.workflows import build_dynamic_graph, build_static_graph, run_workflow

PREVIEW_CHARS = 160

# what the router decided the question needs
ROUTE_LABELS = {
    "rules": "rules (needs the CBA only)",
    "data": "data (needs team numbers only)",
    "both": "both (needs the CBA and team numbers)",
    "clarify": "clarify (too vague, needs to ask first)",
}

# what to print as each step finishes
STEP_LABELS = {
    "route": "Read the question",
    "clarify": "Needs more detail",
    "rules": "Searched the CBA",
    "data": "Looked up team numbers",
    "compose": "Wrote the answer",
    "verify": "Checked the answer",
    "revise": "Answer failed a check, retrying",
    "abstain": "Not confident enough to answer",
}


def parse_args():
    parser = argparse.ArgumentParser(description="NBA Cap and Trade Advisor")
    parser.add_argument("question", help="the question to ask, in quotes")
    parser.add_argument("--mode", choices=["static", "dynamic"], default="dynamic", help="which workflow to run")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="how many chunks to retrieve")
    parser.add_argument("--tier", choices=["core", "maybe"], help="only search this tier")
    parser.add_argument("--show-chunks", action="store_true", help="also print the retrieved chunks and any reworded search")
    return parser.parse_args()


def build_graph(mode):
    """Pick the workflow to run."""
    if mode == "static":
        return build_static_graph()
    return build_dynamic_graph()


def show_step(step):
    """Print one line of progress as soon as a step finishes."""
    print("  - " + STEP_LABELS.get(step, step), flush=True)


def run_with_clarifying(graph, question, top_k, tier):
    """Run the workflow, asking the user for more detail whenever it needs it."""
    clarify_count = 0

    while True:
        print("\nWorking on it...", flush=True)
        result = run_workflow(graph, question, top_k, tier, clarify_count, show_step)

        # an answer or a refusal means we're done
        if result["composed"] is not None:
            return question, result

        # no answer means the graph stopped to ask a question
        reply = input("\n" + result["clarify_question"] + " ")
        question = question + " " + reply
        clarify_count = result["clarify_count"]


def print_search(rules_result, show_rewrite):
    """Print how the CBA search went."""
    print(f"Best score: {rules_result['best_score']:.3f} (passed: {rules_result['passed']})")

    if show_rewrite and rules_result["rewritten_query"]:
        print(f"Reworded as: {rules_result['rewritten_query']}")


def print_chunks(chunks):
    """Print each retrieved chunk with its score, citation, pages, tier and a short preview."""
    for rank, chunk in enumerate(chunks, start=1):
        body = chunk["text"].split("\n", 1)[1]
        print(f"{rank}. [{chunk['score']:.3f}] {chunk['citation']} (p. {chunk['pages']}, {chunk['tier']})")
        print(f"   {body[:PREVIEW_CHARS]}...\n")


def print_result(result, show_rewrite=False):
    """Print the path the question took, the checks, and the answer."""
    print("Route: " + ROUTE_LABELS.get(result["route"], str(result["route"])))
    print("Steps: " + " -> ".join(result["steps"]))

    # the CBA search is skipped on some routes
    if result["rules_result"] is not None:
        print_search(result["rules_result"], show_rewrite)

    # the verifier is skipped if the run stopped early
    if result["verdict"] is not None:
        print(f"Verified: {result['verdict']['passed']} ({result['verdict']['reason']})")

    print(f"\nAnswer: {result['composed']['answer']}\n")


def main():
    args = parse_args()
    graph = build_graph(args.mode)

    question, result = run_with_clarifying(graph, args.question, args.top_k, args.tier)

    print(f"\nQuestion: {question}")
    print(f"Settings: mode={args.mode}, top_k={args.top_k}, tier={args.tier or 'all'}\n")
    print_result(result, args.show_chunks)

    if args.show_chunks and result["rules_result"] is not None:
        print_chunks(result["rules_result"]["chunks"])


if __name__ == "__main__":
    main()
