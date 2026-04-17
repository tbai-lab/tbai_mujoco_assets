"""Command-line interface for tbai_mujoco_assets.

Usage
-----
    tbai-mujoco-assets fetch libero dimos
    tbai-mujoco-assets fetch --all
    tbai-mujoco-assets list
    tbai-mujoco-assets list-worlds
    tbai-mujoco-assets list-robots
"""

from __future__ import annotations

import argparse
import sys

from . import _fetch


def _cmd_fetch(args: argparse.Namespace) -> int:
    groups: list[str] = list(args.groups)
    if args.all:
        groups = list(_fetch.GROUPS)
    if not groups:
        print("error: specify at least one group or --all", file=sys.stderr)
        print(f"known groups: {', '.join(_fetch.GROUPS)}", file=sys.stderr)
        return 2
    for group in groups:
        if group not in _fetch.MANIFEST:
            print(
                f"error: unknown group {group!r}. known: {', '.join(_fetch.GROUPS)}",
                file=sys.stderr,
            )
            return 2
    for group in groups:
        path = _fetch.ensure_group(group, force=args.force)
        print(f"{group}: {path}")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    for group in _fetch.GROUPS:
        try:
            path = _fetch.group_dir(group, fetch=False)
            status = f"ready ({path})"
        except FileNotFoundError:
            status = "not fetched"
        print(f"{group}: {status}")
    return 0


def _cmd_list_worlds(args: argparse.Namespace) -> int:
    from tbai_mujoco_assets import list_worlds

    if args.fetch:
        for group in _fetch.GROUPS:
            _fetch.ensure_group(group)
    worlds = list_worlds()
    if not worlds:
        print(
            "no worlds found locally. Run `tbai-mujoco-assets fetch --all` first "
            "or re-run with `--fetch`.",
            file=sys.stderr,
        )
        return 1
    for world in worlds:
        print(world)
    return 0


def _cmd_list_robots(_args: argparse.Namespace) -> int:
    try:
        import tbai_mujoco_descriptions as desc
    except ImportError:
        print(
            "error: tbai_mujoco_descriptions is not installed.",
            file=sys.stderr,
        )
        return 1
    for robot in desc.AVAILABLE_ROBOTS:
        print(robot)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tbai-mujoco-assets")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="download asset groups into the cache")
    p_fetch.add_argument("groups", nargs="*", help=f"one or more of: {', '.join(_fetch.GROUPS)}")
    p_fetch.add_argument("--all", action="store_true", help="fetch every known group")
    p_fetch.add_argument("--force", action="store_true", help="re-download even if cached")
    p_fetch.set_defaults(func=_cmd_fetch)

    p_list = sub.add_parser("list", help="show which groups are available locally")
    p_list.set_defaults(func=_cmd_list)

    p_worlds = sub.add_parser("list-worlds", help="list worlds available locally")
    p_worlds.add_argument(
        "--fetch", action="store_true", help="fetch all groups first"
    )
    p_worlds.set_defaults(func=_cmd_list_worlds)

    p_robots = sub.add_parser(
        "list-robots", help="list robots available via tbai_mujoco_descriptions"
    )
    p_robots.set_defaults(func=_cmd_list_robots)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
