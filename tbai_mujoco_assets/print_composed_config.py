"""CLI: compose a robot+world and print the tbai_mujoco config path.

Usage
-----
    python -m tbai_mujoco_assets.print_composed_config --robot go2 --world libero
    python -m tbai_mujoco_assets.print_composed_config --robot anymal_d --world dimos/office1 --pos "1 0 0.6"
    tbai_mujoco $(python -m tbai_mujoco_assets.print_composed_config -r go2 -w dimos/empty)
"""

import argparse

from .compose import ComposeSpec, compose, parse_floats


parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
parser.add_argument("-r", "--robot", required=True, help="robot name (from tbai_mujoco_descriptions)")
parser.add_argument("-w", "--world", required=True, help="world name (from tbai_mujoco_assets, e.g. 'libero' or 'dimos/office1')")
parser.add_argument("-p", "--pos", default=None, help="absolute world-frame spawn position 'x y z' for the robot's root body. Omit to keep the robot's MJCF rest pose.")
parser.add_argument("-q", "--quat", default=None, help="absolute world-frame spawn quaternion 'w x y z'. Omit to keep the robot's MJCF rest pose.")
parser.add_argument("-f", "--force", action="store_true", help="rebuild even if cached")
args = parser.parse_args()

spec = ComposeSpec(
    robot=args.robot,
    world=args.world,
    pos=parse_floats(args.pos, 3) if args.pos is not None else None,
    quat=parse_floats(args.quat, 4) if args.quat is not None else None,
)
print(compose(spec, force=args.force))
