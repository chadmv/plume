"""The `plume` command line: parses arguments and dispatches to a subcommand."""

import argparse
import sys
import typing
from pathlib import Path

from plume import tool_label
from plume.recipe.errors import RecipeError
from plume.sheet.assemble import GutterError
from plume.sheet.crop import NothingVisibleError
from plume.sim.device import DeviceError

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_RECIPE_ERROR = 2
EXIT_USAGE = 64  # the BSD sysexits EX_USAGE code; argparse's own 2 would read as a recipe error


class _Parser(argparse.ArgumentParser):
    """An argument parser whose usage errors exit with EXIT_USAGE, apart from recipe errors."""

    def error(self, message: str) -> typing.NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def main(argv: list[str] | None = None) -> int:
    """Runs the command line and returns its exit code."""
    argv = sys.argv[1:] if argv is None else argv
    args = _parser().parse_args(argv)
    try:
        if args.command == "version":
            print(tool_label())
            return EXIT_OK
        if args.command == "check":
            from plume.cli.check import run_check

            run_check(Path(args.recipe), preview=args.preview, sets=tuple(args.set))
            return EXIT_OK
        from plume.cli.run import run_recipe

        run_recipe(Path(args.recipe), preview=args.preview, device=args.device, out=args.out, sets=tuple(args.set),
                   command=" ".join(["plume", *argv]))
        return EXIT_OK
    except RecipeError as error:
        print(f"recipe error: {error}", file=sys.stderr)
        return EXIT_RECIPE_ERROR
    except (DeviceError, NothingVisibleError, GutterError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILED


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="plume", description="Fire, smoke and explosion flipbooks.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="print the tool's name and version")

    check = commands.add_parser("check", help="validate a recipe and print its resolved settings")
    check.add_argument("recipe", help="path to the recipe TOML")
    check.add_argument("--preview", action="store_true", help="resolve with --preview overrides")
    _add_set_argument(check)

    run = commands.add_parser("run", help="simulate a recipe and write the sheet and reports")
    run.add_argument("recipe", help="path to the recipe TOML")
    run.add_argument("--preview", action="store_true", help="low resolution, few frames, for a quick look")
    run.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto",
                     help="where to simulate; auto uses the GPU when there is one")
    run.add_argument("--out", help="output folder; default out/<name>/")
    _add_set_argument(run)
    return parser


def _add_set_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override one recipe value, for example forces.drag_per_s=0.5 or "
                             "emitter.puff.radius_m=0.4; repeatable")


if __name__ == "__main__":
    sys.exit(main())
