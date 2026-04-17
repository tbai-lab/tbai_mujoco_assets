# tbai_mujoco_assets

MuJoCo world/scene assets for [`tbai_mujoco`](https://github.com/tbai-lab/tbai_mujoco). Complements [`tbai_mujoco_descriptions`](https://github.com/tbai-lab/tbai_mujoco_descriptions).

## Sources

| Group    | Upstream |
| ---      | --- |
| `libero` | [LIBERO](https://libero-project.github.io/) tabletop benchmark (kitchen / living room / study scenes + object catalogue) |
| `dimos`  | [dimos](https://github.com/dimensionalOS/dimos) office scene, empty ground plane, standalone person asset |

## Install & use

```bash
pip install "git+ssh://git@github.com/tbai-lab/tbai_mujoco_assets.git"

tbai-mujoco-assets list                        # show which groups are cached
tbai-mujoco-assets fetch libero                # prefetch (also: dimos, --all, --force)
tbai-mujoco-assets list-worlds                 # list worlds available locally (--fetch to grab all first)
tbai-mujoco-assets list-robots                 # list robots from tbai_mujoco_descriptions
```

Tarballs are pulled from this repo's GitHub Releases into `$XDG_CACHE_HOME/tbai_mujoco_assets/worlds/` (generally `~/.cache/tbai_mujoco_assets/worlds/`).

Set `$TBAI_MUJOCO_ASSETS_WORLDS_DIR` to point the resolver at a `worlds/` checkout outside the installed package (useful when editing assets from a different working copy).

## Maintainers: cutting a release

Build reproducible archives, update the sha256 values in `tbai_mujoco_assets/_fetch.py::MANIFEST`, and upload to a GitHub Release whose tag matches `_ASSETS_RELEASE_TAG`:

```bash
mkdir -p dist
for g in libero dimos; do
  tar -C worlds --sort=name --mtime='1970-01-01' \
      --owner=0 --group=0 --numeric-owner \
      -cf - "$g" | gzip -n > "dist/$g.tar.gz"
done
sha256sum dist/*.tar.gz
gh release create assets-v0.1.1 dist/*.tar.gz
```
