"""Compose a robot (from ``tbai_mujoco_descriptions``) with a world (from ``tbai_mujoco_assets``).

MuJoCo's ``<include>`` does not apply the included file's ``<compiler meshdir>``
when the including file lives in a different directory, so we cannot just write
a tiny ``scene.xml`` that includes a robot XML and a world XML from opposite
sides of the filesystem. Instead we use the ``mjSpec`` API: load both sides as
specs, rewrite every ``mesh``/``texture``/``hfield`` ``file`` attribute to an
absolute path (so the composed XML works from any directory), attach the robot
to the world's worldbody, and serialize.

The result is cached under ``XDG_CACHE_HOME/tbai_mujoco_assets/composed/<key>/``
so repeat invocations are fast. Pass ``force=True`` (or ``--force`` on the CLI)
to rebuild.
"""

from __future__ import annotations

import functools
import hashlib
import os
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

from . import get_scene_path as _get_world_scene_path


def _cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "tbai_mujoco_assets" / "composed"


@dataclass(frozen=True)
class ComposeSpec:
    robot: str
    world: str
    pos: tuple[float, float, float] | None = None
    quat: tuple[float, float, float, float] | None = None

    @functools.cache
    def cache_key(self) -> str:
        payload = f"{self.robot}|{self.world}|{self.pos}|{self.quat}"
        digest = hashlib.sha1(payload.encode()).hexdigest()[:12]
        safe = f"{self.robot}__{self.world}".replace("/", "_")
        return f"{safe}_{digest}"


def _absolutize(spec, source_xml: Path) -> None:
    """Rewrite mesh/texture/hfield file refs on ``spec`` to absolute paths.

    MuJoCo resolves relative file paths against the main XML's directory at
    load time. If we serialize a composed model to a different directory, those
    relative refs break. Absolutizing sidesteps the problem entirely.
    """
    src_dir = source_xml.resolve().parent
    meshdir = (src_dir / spec.meshdir).resolve() if spec.meshdir else src_dir
    texturedir = (src_dir / spec.texturedir).resolve() if spec.texturedir else src_dir
    for mesh in spec.meshes:
        if mesh.file and not os.path.isabs(mesh.file):
            mesh.file = str((meshdir / mesh.file).resolve())
    for tex in spec.textures:
        if tex.file and not os.path.isabs(tex.file):
            tex.file = str((texturedir / tex.file).resolve())
    for hf in spec.hfields:
        if hf.file and not os.path.isabs(hf.file):
            hf.file = str((meshdir / hf.file).resolve())
    spec.meshdir = ""
    spec.texturedir = ""


def _flatten_empty_defaults(parent: ET.Element) -> None:
    """Unwrap ``<default>`` children that have no ``class`` attribute.

    ``mjSpec.attach(..., prefix="")`` serializes with an extra layer of
    unnamed ``<default>`` wrapping around the attached spec's default tree.
    MuJoCo's in-memory compiler is fine with that, but reloading the
    serialized XML raises "empty class name" because non-root ``<default>``
    elements require a ``class`` attribute. We flatten such wrappers by moving
    all their children (whether nested defaults or per-element defaults like
    ``<geom>``/``<material>``) up into the parent, which is semantically
    equivalent — an unnamed intermediate default simply inherited from its
    parent.
    """
    for child in list(parent.findall("default")):
        if not child.attrib:
            idx = list(parent).index(child)
            for i, sub in enumerate(list(child)):
                parent.insert(idx + i, sub)
            parent.remove(child)
    for child in list(parent):
        _flatten_empty_defaults(child)


def _postprocess_xml(xml_str: str) -> str:
    root = ET.fromstring(xml_str)
    defaults = root.find("default")
    if defaults is not None:
        _flatten_empty_defaults(defaults)
    return ET.tostring(root, encoding="unicode")


def _merge_config(robot_config_path: Path, composed_scene: Path) -> dict:
    with robot_config_path.open() as f:
        cfg = yaml.safe_load(f) or {}
    cfg["robot_scene"] = str(composed_scene)
    return cfg


def compose(spec: ComposeSpec, *, force: bool = False) -> Path:
    """Generate a composed scene + config for ``spec`` and return the config path.

    The composed output directory is cached; on a cache hit, the existing
    config path is returned without rebuilding. Pass ``force=True`` to rebuild.

    Cache invalidates automatically when the robot MJCF, robot config.yaml, or
    world scene.xml source files are modified (their mtimes feed the key).
    """
    import mujoco as mj  # local import keeps module import cheap
    import tbai_mujoco_descriptions as desc

    robot_mjcf = Path(desc.get_mjcf_path(spec.robot))
    robot_config = Path(desc.get_config_path(spec.robot))
    world_scene = _get_world_scene_path(spec.world)

    # Include source-file mtimes in the cache key so edits to a robot's MJCF
    # or the world XML invalidate stale composed scenes automatically.
    mtimes = "|".join(
        f"{p.stat().st_mtime_ns}" for p in (robot_mjcf, robot_config, world_scene)
    )
    cache_payload = f"{spec.cache_key()}|{mtimes}"
    cache_digest = hashlib.sha1(cache_payload.encode()).hexdigest()[:12]
    out_dir = _cache_root() / f"{spec.cache_key()}_{cache_digest}"
    scene_out = out_dir / "scene.xml"
    config_out = out_dir / "config.yaml"
    if config_out.exists() and scene_out.exists() and not force:
        return config_out

    world_mj = mj.MjSpec.from_file(str(world_scene))
    robot_mj = mj.MjSpec.from_file(str(robot_mjcf))
    _absolutize(world_mj, world_scene)
    _absolutize(robot_mj, robot_mjcf)

    # mjSpec.attach() keeps only the world's <option>, so robot-level contact
    # settings (cone, impratio, timestep, etc.) get silently dropped. For
    # legged robots this is a big deal: go2.xml declares cone="elliptic"
    # impratio="100", and without those the composed scene falls back to
    # pyramidal cone + impratio=1, causing spongy/unreliable foot contacts.
    # Copy the robot's option fields onto the world so they survive.
    for attr in ("cone", "impratio", "timestep", "integrator", "iterations",
                 "tolerance", "noslip_iterations", "noslip_tolerance"):
        if hasattr(robot_mj.option, attr) and hasattr(world_mj.option, attr):
            setattr(world_mj.option, attr, getattr(robot_mj.option, attr))

    # When the caller supplies an explicit pos/quat, treat it as an ABSOLUTE
    # world-frame pose for the robot's root body. mjSpec.attach composes the
    # frame transform with each root body's existing pos/quat, so to make the
    # frame pose absolute we zero out the root body(ies) first. Without an
    # explicit pose we leave the robot's MJCF-declared rest pose alone (e.g.
    # go2 base_link at z=0.445).
    if spec.pos is not None or spec.quat is not None:
        for body in robot_mj.worldbody.bodies:
            body.pos = [0.0, 0.0, 0.0]
            body.quat = [1.0, 0.0, 0.0, 0.0]

    frame = world_mj.worldbody.add_frame()
    frame.pos = list(spec.pos) if spec.pos is not None else [0.0, 0.0, 0.0]
    frame.quat = list(spec.quat) if spec.quat is not None else [1.0, 0.0, 0.0, 0.0]
    # ``prefix=""`` keeps the robot's MJCF names (cameras, sensors, bodies)
    # unprefixed. Without this the default prefix is ``/`` so e.g.
    # ``wrist_camera`` becomes ``/wrist_camera``, tbai_mujoco's config.yaml
    # still asks for ``wrist_camera`` (VideoServer reports "camera not found"),
    # and the hardcoded ``imu_quat``/``imu_gyro``/``imu_acc`` sensor lookups in
    # tbai_bridge silently fail the same way.
    world_mj.attach(robot_mj, frame=frame, prefix="")

    # Fail fast on compile errors rather than only at runtime inside tbai_mujoco.
    world_mj.compile()

    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene_out.write_text(_postprocess_xml(world_mj.to_xml()))
    merged = _merge_config(robot_config, scene_out)
    with config_out.open("w") as f:
        yaml.safe_dump(merged, f, sort_keys=False)
    return config_out


def parse_floats(text: str, n: int) -> tuple[float, ...]:
    parts = [float(x) for x in text.replace(",", " ").split()]
    if len(parts) != n:
        raise ValueError(f"expected {n} floats, got {len(parts)}: {text!r}")
    return tuple(parts)
