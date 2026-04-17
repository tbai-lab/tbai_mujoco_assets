import argparse

from . import get_world_path

parser = argparse.ArgumentParser()
parser.add_argument("world")
print(get_world_path(parser.parse_args().world))
