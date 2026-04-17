import argparse

from . import get_config_path

parser = argparse.ArgumentParser()
parser.add_argument("world")
print(get_config_path(parser.parse_args().world))
