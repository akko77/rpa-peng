"""Template image library file management.

Layout on disk:
    templates/
      <group_name>/
        v1.png
        v2.png
        meta.json        ← Phase 2.1: written on every group modification

The TemplateGroup data also lives in the workflow JSON. The on-disk meta.json
is redundant by design — it lets users import existing templates into a fresh
workflow, and acts as a backup of the metadata if a workflow JSON is lost.

On load, the workflow JSON wins. meta.json is read only on explicit import.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_META_FILENAME = "meta.json"


def sanitize_group_name(name: str) -> str:
    s = _INVALID.sub("_", (name or "").strip())
    return s or "untitled"


def group_dir(templates_root: Union[str, Path], group_name: str) -> Path:
    return Path(templates_root) / sanitize_group_name(group_name)


def next_variant_filename(templates_root: Union[str, Path], group_name: str) -> str:
    d = group_dir(templates_root, group_name)
    if not d.exists():
        return "v1.png"
    existing = set(p.name for p in d.glob("*.png"))
    i = 1
    while f"v{i}.png" in existing:
        i += 1
    return f"v{i}.png"


def save_variant_image(
    templates_root: Union[str, Path],
    group_name: str,
    image,
    filename: Optional[str] = None,
) -> Tuple[str, str]:
    d = group_dir(templates_root, group_name)
    d.mkdir(parents=True, exist_ok=True)
    fn = filename or next_variant_filename(templates_root, group_name)
    if not fn.lower().endswith(".png"):
        fn += ".png"
    full = d / fn
    image.save(str(full), format="PNG")
    return fn, str(full)


def variant_image_path(
    templates_root: Union[str, Path], group_name: str, filename: str
) -> Path:
    return group_dir(templates_root, group_name) / filename


def today_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def delete_variant(templates_root: Union[str, Path], group_name: str, filename: str) -> bool:
    p = variant_image_path(templates_root, group_name, filename)
    if p.exists():
        p.unlink()
        return True
    return False


def delete_group(templates_root: Union[str, Path], group_name: str) -> bool:
    import shutil
    d = group_dir(templates_root, group_name)
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


# ------------------ meta.json read/write ------------------

def write_group_meta(templates_root: Union[str, Path], group) -> None:
    """Persist a TemplateGroup's metadata to <group_dir>/meta.json.

    Best-effort: errors are swallowed and logged via the standard logger,
    since meta.json is redundant (workflow JSON is the source of truth).
    """
    import logging
    try:
        d = group_dir(templates_root, group.name)
        d.mkdir(parents=True, exist_ok=True)
        with (d / _META_FILENAME).open("w", encoding="utf-8") as f:
            json.dump(group.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.getLogger(__name__).warning(f"write_group_meta failed for {group.name!r}: {e}")


def read_group_meta(templates_root: Union[str, Path], group_name: str):
    """Read meta.json for a group and return a TemplateGroup, or None on error/missing."""
    from ..core.workflow import TemplateGroup
    d = group_dir(templates_root, group_name)
    meta = d / _META_FILENAME
    if not meta.exists():
        return None
    try:
        with meta.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return TemplateGroup.from_dict(data)
    except Exception:
        return None


def build_group_from_disk(templates_root: Union[str, Path], group_name: str):
    """Build a TemplateGroup by scanning the on-disk folder.

    Prefers meta.json if present; otherwise reconstructs from PNG files using
    sensible defaults (confidence 0.7, no default_region, first_hit strategy).
    Variants found on disk but missing from meta.json are appended.
    """
    from ..core.workflow import TemplateGroup, TemplateVariant
    d = group_dir(templates_root, group_name)
    if not d.exists() or not d.is_dir():
        return None

    on_disk = sorted(p.name for p in d.glob("*.png"))
    if not on_disk:
        return None

    meta_group = read_group_meta(templates_root, group_name)
    if meta_group is not None:
        # Reconcile: keep meta order, append any PNG files not listed
        listed = {v.file for v in meta_group.variants}
        for fn in on_disk:
            if fn not in listed:
                meta_group.variants.append(TemplateVariant(
                    file=fn, confidence=meta_group.default_confidence,
                    added_at=today_string(), note="(disk-only)",
                ))
        # Filter out variants whose file no longer exists
        existing = set(on_disk)
        meta_group.variants = [v for v in meta_group.variants if v.file in existing]
        meta_group.name = group_name  # ensure name matches folder
        return meta_group

    # No meta.json — defaults
    variants = [
        TemplateVariant(file=fn, confidence=0.7, added_at=today_string(), note="")
        for fn in on_disk
    ]
    return TemplateGroup(
        name=group_name,
        variants=variants,
        default_region=None,
        default_confidence=0.7,
        match_strategy="first_hit",
    )


def scan_templates_dir(templates_root: Union[str, Path]) -> List:
    """Return a list of TemplateGroup objects for every subfolder containing PNGs."""
    root = Path(templates_root)
    if not root.exists() or not root.is_dir():
        return []
    out = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        group = build_group_from_disk(root, child.name)
        if group is not None:
            out.append(group)
    return out


def import_groups_from_workflow_file(workflow_path: Union[str, Path]) -> dict:
    """Read a .awf.json and return its templates dict {name: TemplateGroup}."""
    from ..persistence.workflow_io import load_workflow
    wf = load_workflow(workflow_path)
    return wf.templates
