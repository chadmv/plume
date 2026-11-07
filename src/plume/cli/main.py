"""The `plume` command line: parses arguments and dispatches to a subcommand."""

import argparse
import sys

from plume import tool_label


def main(argv: list[str] | None = None) -> int:
    """Runs the command line and returns its exit code."""
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "version":
        print(tool_label())
        return 0
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plume", description="Fire, smoke and explosion flipbooks.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="print the tool's name and version")
    return parser


if __name__ == "__main__":
    sys.exit(main())
