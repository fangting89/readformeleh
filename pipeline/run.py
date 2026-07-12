"""CLI entrypoint: classify then summarize a letter photo from the command line."""

import argparse
from pathlib import Path

from pipeline.classify import classify_letter
from pipeline.summarize import summarize_letter


def main() -> None:
    """CLI entrypoint: classify then summarize a letter photo, if safe to."""
    parser = argparse.ArgumentParser(
        description="Summarize a photographed government letter."
    )
    parser.add_argument("photo", type=Path)
    parser.add_argument("--lang", choices=["en", "zh"], default="en")
    args = parser.parse_args()

    result = classify_letter(args.photo)
    if result["category"] == "suspicious":
        print("This letter looks suspicious:", ", ".join(result["red_flags"]))
        return
    if result["category"] == "unreadable":
        print("Couldn't read this photo clearly — try a clearer, well-lit shot.")
        return

    print(summarize_letter(args.photo, lang=args.lang))


if __name__ == "__main__":
    main()
