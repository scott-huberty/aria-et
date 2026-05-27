"""Command line entry points for ARIA eye-tracking tasks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from aria_et.tasks import BATTERY_ORDER


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aria-et")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-tasks",
        help="Print the configured battery order.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-tasks":
        for task in BATTERY_ORDER:
            print(task.task_id)
        return 0

    raise ValueError(f"Unsupported command: {args.command}")
