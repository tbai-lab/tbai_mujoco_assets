# tbai_mujoco_assets

MuJoCo world/scene assets for use with the [`tbai_mujoco`](https://github.com/tbai-lab/tbai_mujoco) simulator. Complements [`tbai_mujoco_descriptions`](https://github.com/tbai-lab/tbai_mujoco_descriptions) (which ships robot descriptions and two small reference worlds) by packaging larger third-party worlds and scene libraries.

## Worlds shipped

| Name | Source | Description |
| --- | --- | --- |
| `libero` | [LIBERO](https://libero-project.github.io/) | Tabletop manipulation benchmark assets: kitchen / living room / study / floor scene backgrounds plus a catalogue of stable, articulated, and scanned objects. |
| `dimos/office1` | [dimos](https://github.com/dimensionalOS/dimos) | Furnished office scene ("Mersus Office" on Sketchfab by Ryan Cassidy & Coleman Costello). |
| `dimos/empty` | dimos | Minimal ground-plane world. |
| `dimos/person` | dimos | Standalone human asset ("jeong_seun_34" on Sketchfab). Shared; not a standalone world. |

## Install

Asset data (meshes, textures) is **not bundled in the wheel** — it's downloaded lazily from this repo's GitHub Releases on first use into `$XDG_CACHE_HOME/tbai_mujoco_assets/worlds/`. Extras are named after asset groups so you can advertise which ones you'll use:

```bash
pip install tbai-mujoco-assets                 # code only
pip install "tbai-mujoco-assets[libero]"       # code only; libero fetched on first use
pip install "tbai-mujoco-assets[libero,dimos]" # ditto, both groups
pip install "tbai-mujoco-assets[all]"
```

Note: the extras themselves don't trigger the download (pip can't run code at install time for wheels). The fetch happens on first call to `get_world_path(...)`. To prefetch eagerly:

```bash
tbai-mujoco-assets fetch libero          # or: dimos, or both
tbai-mujoco-assets fetch --all
tbai-mujoco-assets list                  # show what's cached
```

### Dev install (from a clone)

Asset data is **not committed** to this repo (`worlds/` is gitignored) — it only lives in the GitHub Release tarballs. Clone, install editable, then fetch into the cache:

```bash
git clone git@github.com:tbai-lab/tbai_mujoco_assets.git
cd tbai_mujoco_assets
pip install -e .
tbai-mujoco-assets fetch --all
```

If you want dev-mode to resolve paths against an in-repo `worlds/` (so the package short-circuits the cache), extract the tarballs there:

```bash
mkdir -p worlds && tar -xzf dist/libero.tar.gz -C worlds && tar -xzf dist/dimos.tar.gz -C worlds
```

`.gitattributes` routes binary extensions under `worlds/**` through Git LFS as a safety net, in case assets are ever (re-)committed later.

## Use with `tbai_mujoco`

### Robot + world (recommended)

Pick any robot from [`tbai_mujoco_descriptions`](https://github.com/tbai-lab/tbai_mujoco_descriptions) (`go2`, `anymal_b/c/d`, `g1`, `spot`, `spot_arm`, `go2w`, `franka_panda`) and any world from here, and the compose helper generates a fused scene:

```bash
# Go2 inside the LIBERO kitchen tabletop
tbai_mujoco "$(python -m tbai_mujoco_assets.print_composed_config -r go2 -w libero --pos '0.5 0 1.1')"

# G1 humanoid walking in the dimos office
tbai_mujoco "$(python -m tbai_mujoco_assets.print_composed_config -r g1 -w dimos/office1)"

# Anymal B on empty ground
tbai_mujoco "$(python -m tbai_mujoco_assets.print_composed_config -r anymal_b -w dimos/empty)"
```

The composed scene + config are cached under `$XDG_CACHE_HOME/tbai_mujoco_assets/composed/<robot>__<world>_<hash>/` keyed on `(robot, world, pos, quat)`. Pass `--force` to rebuild.

### World only

If you just want to inspect a world (no robot attached):

```bash
python -m tbai_mujoco_assets.list_worlds
tbai_mujoco "$(python -m tbai_mujoco_assets.print_config_path libero)"
tbai_mujoco "$(python -m tbai_mujoco_assets.print_config_path dimos/office1)"
```

## Python API

```python
from tbai_mujoco_assets import (
    list_groups,      # fetchable asset groups: ['dimos', 'libero']
    list_worlds,      # worlds available locally (no download triggered)
    ensure_group,     # prefetch a group into the cache
    get_world_path,   # triggers download of owning group on first use
    get_scene_path,
    get_config_path,
    compose,          # (robot, world, pos=(0,0,0), quat=(1,0,0,0)) -> Path to config.yaml
)
```

## Cutting a release (maintainers)

Build reproducible archives and update the sha256 values in `tbai_mujoco_assets/_fetch.py::MANIFEST`, then upload to a GitHub Release whose tag matches `_ASSETS_RELEASE_TAG`:

```bash
mkdir -p dist
for group in libero dimos; do
  tar -C worlds --sort=name --mtime='1970-01-01' \
      --owner=0 --group=0 --numeric-owner \
      -cf - "$group" | gzip -n > "dist/$group.tar.gz"
done
sha256sum dist/*.tar.gz
gh release create assets-v0.1.0 dist/libero.tar.gz dist/dimos.tar.gz
```

## How composing works

MuJoCo's `<include>` does not honour the included file's `<compiler meshdir>` when the main XML lives in a different directory, so we can't just write a thin wrapper that includes a robot XML and a world XML from opposite ends of the filesystem. `tbai_mujoco_assets.compose` therefore:

1. Loads the world and robot as `mjSpec` objects.
2. Rewrites every `<mesh>`/`<texture>`/`<hfield>` `file=` attribute to an absolute path (using each spec's own `meshdir`/`texturedir`), then clears the compiler dirs.
3. Adds a frame at the world's `worldbody` at the requested pos/quat and calls `world.attach(robot, frame=...)`.
4. Compiles (fail-fast) and serializes to `scene.xml` alongside a merged `config.yaml` copied from the robot's config with `robot_scene` pointed at the composed scene.

## Layout

```
tbai_mujoco_assets/
├── pyproject.toml
├── tbai_mujoco_assets/                  # Python package
│   ├── __init__.py                      # API: list_worlds / get_* / compose
│   ├── compose.py                       # mjSpec-based robot+world composition
│   ├── list_worlds.py                   # python -m ... list_worlds
│   ├── print_config_path.py             # python -m ... print_config_path <world>
│   ├── print_composed_config.py         # python -m ... print_composed_config -r <robot> -w <world>
│   ├── print_scene_path.py
│   └── print_world_path.py
└── worlds/
    ├── libero/
    └── dimos/
        ├── office1/
        ├── empty/
        └── person/
```

Each world directory ships a `config.yaml` consumable directly by the `tbai_mujoco` binary. Composed (robot+world) configs are generated on demand under `$XDG_CACHE_HOME/tbai_mujoco_assets/composed/`.
