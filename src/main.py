import argparse
from src.config import TOP_K
from src.tools.retrieval import search_cba

PREVIEW_CHARS = 160


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NBA Cap and Trade Advisor")
    parser.add_argument("question", help="the question to ask, in quotes")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="how many chunks to retrieve")
    parser.add_argument("--tier", choices=["core", "maybe"], help="only search this tier")
    return parser.parse_args()


def main():
    args = parse_args()
    results = search_cba(args.question, top_k=args.top_k, tier=args.tier)

    print(f"\nQuestion: {args.question}")
    print(f"Settings: top_k={args.top_k}, tier={args.tier or 'all'}\n")
    for rank, result in enumerate(results, start=1):
        body = result["text"].split("\n", 1)[1]
        print(f"{rank}. [{result['score']:.3f}] {result['citation']} (p. {result['pages']}, {result['tier']})")
        print(f"   {body[:PREVIEW_CHARS]}...\n")


if __name__ == "__main__":
    main()
