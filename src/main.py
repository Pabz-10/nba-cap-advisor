import argparse
from src.config import TOP_K
from src.agents.rules_agent import run_rules_agent
from src.agents.composer import compose_answer

PREVIEW_CHARS = 160


def parse_args():
    parser = argparse.ArgumentParser(description="NBA Cap and Trade Advisor")
    parser.add_argument("question", help="the question to ask, in quotes")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="how many chunks to retrieve")
    parser.add_argument("--tier", choices=["core", "maybe"], help="only search this tier")
    parser.add_argument("--show-chunks", action="store_true", help="also print the retrieved chunks")
    return parser.parse_args()


def print_chunks(chunks):
    # prints each retrieved chunk with its score, citation, pages, tier and a short preview
    for rank, chunk in enumerate(chunks, start=1):
        body = chunk["text"].split("\n", 1)[1]
        print(f"{rank}. [{chunk['score']:.3f}] {chunk['citation']} (p. {chunk['pages']}, {chunk['tier']})")
        print(f"   {body[:PREVIEW_CHARS]}...\n")


def main():
    args = parse_args()

    # run the rules agent with the question, top_k and tier
    rules_agent_res = run_rules_agent(args.question, args.top_k, args.tier)

    # run the composer with the question and the rules result
    composer_res = compose_answer(args.question, rules_agent_res)

    print(f"\nQuestion: {args.question}")
    print(f"Settings: top_k={args.top_k}, tier={args.tier or 'all'}\n")

    # if a rewrite was used, print the reworded question
    if rules_agent_res["rewritten_query"]:
        print(f"Reworded as: {rules_agent_res['rewritten_query']}")

    # print the best score and whether it passed
    print(f"Best score: {rules_agent_res['best_score']:.3f} (passed: {rules_agent_res['passed']})\n")

    # print the answer
    print(f"Answer: {composer_res['answer']}\n")

    # if --show-chunks was passed, print the chunks the answer was built from
    if args.show_chunks:
        print_chunks(rules_agent_res["chunks"])


if __name__ == "__main__":
    main()
