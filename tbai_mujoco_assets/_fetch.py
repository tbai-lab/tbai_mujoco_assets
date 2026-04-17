"""Lazy fetch of world asset groups from GitHub Releases.

World names used by the public API (e.g. ``libero``, ``dimos/office1``) map to
*groups* — archives shipped as release assets. ``libero`` is one group;
everything under ``dimos/`` lives in the ``dimos`` group.

Resolution order for a world path:

1. If a sibling ``worlds/<group>`` directory exists next to the installed
   package (editable install from a repo clone, or sdist with data), use it.
2. Otherwise, use ``$XDG_CACHE_HOME/tbai_mujoco_assets/worlds/<group>``;
   download + extract on first miss.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_ASSETS_RELEASE_TAG = "assets-v0.1.1"
_ASSETS_BASE_URL = (
    f"https://github.com/tbai-lab/tbai_mujoco_assets/releases/download/{_ASSETS_RELEASE_TAG}"
)


@dataclass(frozen=True)
class _GroupSpec:
    name: str
    archive: str
    sha256: str | None = None  # fill in once the release is cut

    @property
    def url(self) -> str:
        return f"{_ASSETS_BASE_URL}/{self.archive}"


MANIFEST: dict[str, _GroupSpec] = {
    "libero": _GroupSpec(
        name="libero",
        archive="libero.tar.gz",
        sha256="6e3bd4c6e9496fe559fd511c4275df87cf2d85a10e65ddd22e8231d39d45b67f",
    ),
    "dimos": _GroupSpec(
        name="dimos",
        archive="dimos.tar.gz",
        sha256="2a9cd92956b4da8acc6ab179473ebdbea60392fdc7ee43967f27b704eeae6ab9",
    ),
}

GROUPS = tuple(MANIFEST.keys())

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_WORLDS_DIR = _PACKAGE_DIR.parent / "worlds"


def group_for_world(world: str) -> str:
    """Return the asset group that owns ``world`` (e.g. ``dimos/office1`` → ``dimos``)."""
    head = world.split("/", 1)[0]
    if head not in MANIFEST:
        raise ValueError(
            f"Unknown world {world!r}. Known groups: {sorted(MANIFEST)}"
        )
    return head


def cache_root() -> Path:
    """Base cache dir for downloaded asset groups."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "tbai_mujoco_assets" / "worlds"


def _repo_group_dir(group: str) -> Path | None:
    """Return the in-repo ``worlds/<group>`` dir if it exists (dev mode)."""
    candidate = _REPO_WORLDS_DIR / group
    return candidate if candidate.is_dir() else None


def group_dir(group: str, *, fetch: bool = True) -> Path:
    """Return the directory containing ``worlds/<group>`` contents.

    Dev mode (sibling ``worlds/`` in the repo) is preferred. Otherwise the
    cached copy is used, downloaded on first access unless ``fetch=False``.
    """
    if group not in MANIFEST:
        raise ValueError(f"Unknown group {group!r}. Known: {sorted(MANIFEST)}")
    repo = _repo_group_dir(group)
    if repo is not None:
        return repo
    cached = cache_root() / group
    if cached.is_dir():
        return cached
    if not fetch:
        raise FileNotFoundError(
            f"Group {group!r} is not available locally. "
            f"Run `tbai-mujoco-assets fetch {group}` or call ensure_group({group!r})."
        )
    _download_and_extract(MANIFEST[group], cached)
    return cached


def ensure_group(group: str, *, force: bool = False) -> Path:
    """Download ``group`` into the cache if missing (or if ``force``).

    In dev mode the in-repo copy is used and no download occurs.
    """
    if group not in MANIFEST:
        raise ValueError(f"Unknown group {group!r}. Known: {sorted(MANIFEST)}")
    if _repo_group_dir(group) is not None and not force:
        return _repo_group_dir(group)  # type: ignore[return-value]
    cached = cache_root() / group
    if force and cached.is_dir():
        shutil.rmtree(cached)
    if not cached.is_dir():
        _download_and_extract(MANIFEST[group], cached)
    return cached


def worlds_root_for(world: str) -> Path:
    """Directory whose child ``<world>`` is the world dir (handles nested worlds)."""
    group = group_for_world(world)
    gdir = group_dir(group)
    # world is either "<group>" (single-dir group) or "<group>/<sub>/..."
    if world == group:
        return gdir.parent
    # e.g. world="dimos/office1", gdir points at ".../dimos" → root is ".../"
    return gdir.parent


def _download_and_extract(spec: _GroupSpec, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[tbai_mujoco_assets] downloading {spec.name} from {spec.url}")
    with tempfile.TemporaryDirectory(prefix=f"tbai-assets-{spec.name}-") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / spec.archive
        with urllib.request.urlopen(spec.url) as resp, archive.open("wb") as f:
            _copy_with_progress(resp, f, spec.archive)
        if spec.sha256:
            actual = _sha256(archive)
            if actual != spec.sha256:
                raise RuntimeError(
                    f"Checksum mismatch for {spec.archive}: "
                    f"expected {spec.sha256}, got {actual}"
                )
        extract_into = tmp_path / "extracted"
        extract_into.mkdir()
        with tarfile.open(archive, "r:*") as tar:
            _safe_extract(tar, extract_into)
        # Archive is expected to contain a single top-level dir named <group>.
        # Fall back to the extract root if the layout is flat.
        payload = extract_into / spec.name
        if not payload.is_dir():
            payload = extract_into
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish: rename into place (both on same filesystem via cache_root).
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(payload), str(dest))


def _copy_with_progress(resp, dst, label: str, chunk: int = 1 << 16) -> None:
    total = resp.length  # None if Content-Length absent
    try:
        from tqdm import tqdm
    except ImportError:
        shutil.copyfileobj(resp, dst)
        return
    with tqdm(
        total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=label
    ) as bar:
        while True:
            buf = resp.read(chunk)
            if not buf:
                break
            dst.write(buf)
            bar.update(len(buf))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract ``tar`` into ``dest``, rejecting paths that escape it."""
    dest = dest.resolve()
    for member in tar.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(dest) + os.sep) and target != dest:
            raise RuntimeError(f"Refusing to extract path outside dest: {member.name}")
    tar.extractall(dest)
