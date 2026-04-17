"""Python API for tbai_mujoco_assets.

A world is a directory under ``worlds/`` that ships a ``scene.xml`` (MuJoCo
model) and a ``config.yaml`` consumable by the ``tbai_mujoco`` binary.

Asset data is grouped (``libero``, ``dimos``) and fetched on demand from
GitHub Releases into ``$XDG_CACHE_HOME/tbai_mujoco_assets/worlds/``. If the
package is installed editable from a repo clone, the in-repo ``worlds/`` tree
is used directly and no download occurs.

Example
-------
>>> from tbai_mujoco_assets import get_config_path, list_worlds
>>> get_config_path("dimos/office1")  # downloads the dimos group if needed
PosixPath('.../worlds/dimos/office1/config.yaml')
"""

from pathlib import Path as _Path

from . import _fetch as _fetch_mod


def list_groups() -> list[str]:
    """Return the names of all fetchable asset groups (e.g. ``['dimos', 'libero']``)."""
    return sorted(_fetch_mod.GROUPS)


def list_worlds() -> list[str]:
    """Return the worlds available *locally* (either in-repo or already cached).

    Does not trigger any downloads. Fetch a group first (via ``ensure_group``
    or the CLI) to have its worlds show up here.
    """
    seen: set[str] = set()
    for group in _fetch_mod.GROUPS:
        try:
            gdir = _fetch_mod.group_dir(group, fetch=False)
        except FileNotFoundError:
            continue
        for cfg in sorted(gdir.rglob("config.yaml")):
            # Worlds live one-or-more levels under the group root; name them
            # relative to the worlds root so "dimos/office1" / "libero" work.
            root = _fetch_mod.worlds_root_for(group)
            seen.add(str(cfg.parent.relative_to(root)))
    return sorted(seen)


def ensure_group(group: str, *, force: bool = False) -> _Path:
    """Ensure asset ``group`` (e.g. ``libero``, ``dimos``) is available locally."""
    return _fetch_mod.ensure_group(group, force=force)


def _world_dir(world: str) -> _Path:
    root = _fetch_mod.worlds_root_for(world)
    path = root / world
    if not path.is_dir():
        raise ValueError(
            f"Unknown world {world!r} in group {_fetch_mod.group_for_world(world)!r}. "
            f"Known locally: {list_worlds()}"
        )
    return path


def get_world_path(world: str) -> _Path:
    """Return the directory that holds ``scene.xml``/``config.yaml`` for ``world``.

    Triggers a download of the owning asset group on first use.
    """
    return _world_dir(world)


def get_scene_path(world: str) -> _Path:
    """Return the path to the world's MuJoCo scene XML.

    Reads the ``robot_scene`` field of ``config.yaml`` (resolved relative to the
    config directory). Falls back to ``scene.xml`` in the world directory.
    """
    import yaml

    config_path = get_config_path(world)
    with config_path.open() as f:
        cfg = yaml.safe_load(f)
    scene_rel = cfg.get("robot_scene", "scene.xml")
    scene = _Path(scene_rel)
    if not scene.is_absolute():
        scene = (config_path.parent / scene).resolve()
    if not scene.exists():
        raise FileNotFoundError(f"robot_scene not found for world {world!r}: {scene}")
    return scene


def get_config_path(world: str) -> _Path:
    """Return the path to the world's ``config.yaml``."""
    path = _world_dir(world) / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config.yaml not found for world {world!r}")
    return path


def compose(
    robot: str,
    world: str,
    pos: tuple[float, float, float] | None = None,
    quat: tuple[float, float, float, float] | None = None,
    *,
    force: bool = False,
) -> _Path:
    """Compose a robot from tbai_mujoco_descriptions with a world from here.

    ``pos``/``quat`` are the ABSOLUTE world-frame spawn pose of the robot's
    root body. When either is omitted the robot keeps its MJCF-declared rest
    pose (e.g. go2 base_link at z=0.445). Returns the path to the generated
    ``config.yaml`` for ``tbai_mujoco``.
    """
    from .compose import ComposeSpec, compose as _compose

    return _compose(ComposeSpec(robot=robot, world=world, pos=pos, quat=quat), force=force)
