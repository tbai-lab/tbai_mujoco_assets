import argparse

from . import get_scene_path

parser = argparse.ArgumentParser()
parser.add_argument("world")
print(get_scene_path(parser.parse_args().world))
