"""Run every eval question through a workflow and score the results.

Run with: python -m eval.run_eval
Compare settings with: python -m eval.run_eval --mode static --top-k 8
Results are saved to eval/results/.
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import get_usage_metadata_callback

from src.agents.verifier import check_citations
from src.config import TOP_K
from src.graph.workflows import build_dynamic_graph, build_static_graph, run_workflow

EVAL_DIR = Path(__file__).parent
QUESTIONS_PATH = EVAL_DIR / "questions.json"
RESULTS_DIR = EVAL_DIR / "results"
DELAY_SECONDS = 1  # short pause between questions, to stay under rate limits


def parse_args():
    parser = argparse.ArgumentParser(description="Score the advisor on the eval questions")
    parser.add_argument("--mode", choices=["static", "dynamic"], default="dynamic", help="which workflow to test")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="how many chunks to retrieve")
    parser.add_argument("--tier", choices=["core", "maybe"], help="only search this tier")
    return parser.parse_args()


def get_behavior(result):
    """Say what the system did: answered, asked a question, or refused."""
    if result["composed"] is None:
        return "clarify"
    if result["composed"]["abstained"]:
        return "abstain"
    return "answer"


def check_answer(question, result, behavior):
    """Did it do the right thing, and if it answered, say the right thing?"""
    if behavior != question["expected_behavior"]:
        return False

    # a correct clarify or abstain has no answer text to check
    if behavior != "answer":
        return True

    answer = result["composed"]["answer"].lower()
    has_expected_text = any(text.lower() in answer for text in question["must_contain_any"])

    # for trades, the pass or fail has to match too
    expected_trade = question["expected_trade_passed"]
    if expected_trade is None:
        return has_expected_text

    data_result = result["data_result"]
    return has_expected_text and data_result is not None and data_result["trade_passed"] == expected_trade


def check_retrieval(question, result):
    """Was the expected CBA section retrieved? None if this question doesn't depend on the CBA."""
    expected = question["expected_citation"]
    if expected is None or not expected.startswith("Article"):
        return None

    if result["rules_result"] is None:
        return False

    # a chunk from a subsection counts, so 8(d)(i) is a hit for 8(d)
    return any(chunk["citation"].startswith(expected) for chunk in result["rules_result"]["chunks"])


def check_citation(question, result, behavior):
    """Are the answer's citations real, and is the expected one there? None if it didn't answer."""
    if behavior != "answer" or question["expected_citation"] is None:
        return None

    answer = result["composed"]["answer"]
    return check_citations(answer, result["composed"]["sources"]) and question["expected_citation"] in answer


def count_tokens(usage):
    """Add up tokens across every model called for one question."""
    return sum(model_usage["total_tokens"] for model_usage in usage.values())


def run_question(graph, question, args):
    """Run one question and record how it did."""
    started = time.time()

    # this counts tokens for every Gemini call made inside the block
    with get_usage_metadata_callback() as tokens:
        result = run_workflow(graph, question["question"], args.top_k, args.tier, question["clarify_count"])

    behavior = get_behavior(result)
    composed = result["composed"]

    return {
        "id": question["id"],
        "type": question["type"],
        "known_gap": question["known_gap"],
        "question": question["question"],
        "route": result["route"],
        "route_correct": result["route"] == question["expected_route"],
        "behavior": behavior,
        "expected_behavior": question["expected_behavior"],
        "behavior_correct": behavior == question["expected_behavior"],
        "correct": check_answer(question, result, behavior),
        "retrieval_hit": check_retrieval(question, result),
        "citation_valid": check_citation(question, result, behavior),
        "verdict": result["verdict"],
        "steps": result["steps"],
        "tokens": count_tokens(tokens.usage_metadata),
        "seconds": round(time.time() - started, 2),
        "answer": composed["answer"] if composed else result["clarify_question"],
    }


def rate(rows, key):
    """Return 'passed/total' for a metric, skipping questions where it doesn't apply."""
    scored = [row[key] for row in rows if row[key] is not None]
    return f"{sum(scored)}/{len(scored)}"


def summarize(rows):
    """Work out the headline numbers. Known gaps are reported separately."""
    main_rows = [row for row in rows if not row["known_gap"]]

    return {
        "questions": len(main_rows),
        "correct": rate(main_rows, "correct"),
        "route_correct": rate(main_rows, "route_correct"),
        "behavior_correct": rate(main_rows, "behavior_correct"),
        "retrieval_hit": rate(main_rows, "retrieval_hit"),
        "citation_valid": rate(main_rows, "citation_valid"),
        "total_tokens": sum(row["tokens"] for row in rows),
        "average_seconds": round(sum(row["seconds"] for row in rows) / len(rows), 2),
        "known_gaps_correct": rate([row for row in rows if row["known_gap"]], "correct"),
    }


def print_report(rows, summary):
    """Print one line per question, then the summary."""
    print(f"\n{'':4} {'id':16} {'route':8} {'did':8} {'tokens':>7} {'secs':>6}")
    for row in rows:
        mark = "ok" if row["correct"] else "FAIL"
        print(f"{mark:4} {row['id']:16} {str(row['route']):8} {row['behavior']:8} {row['tokens']:>7} {row['seconds']:>6}")

    print("\nSummary")
    for name, value in summary.items():
        print(f"  {name}: {value}")


def save_results(rows, summary, args):
    """Save everything to a file so runs can be compared later."""
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{args.mode}_k{args.top_k}_{args.tier or 'all'}_{stamp}.json"

    settings = {"mode": args.mode, "top_k": args.top_k, "tier": args.tier}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"settings": settings, "summary": summary, "results": rows}, f, indent=2)

    print(f"\nSaved to {path}")


def main():
    args = parse_args()
    graph = build_dynamic_graph() if args.mode == "dynamic" else build_static_graph()

    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    rows = []
    for number, question in enumerate(questions, start=1):
        print(f"[{number}/{len(questions)}] {question['id']}")
        rows.append(run_question(graph, question, args))
        time.sleep(DELAY_SECONDS)

    summary = summarize(rows)
    print_report(rows, summary)
    save_results(rows, summary, args)


if __name__ == "__main__":
    main()
