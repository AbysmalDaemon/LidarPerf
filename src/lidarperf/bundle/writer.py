"""Safe one-shot writing and checksum finalization for result bundles."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import ResultManifest, ResultManifestCore


class BundleWriteError(RuntimeError):
    """Raised when a bundle cannot be created without violating immutability rules."""


def _safe_relative_path(path: str | Path) -> str:
    raw_text = str(path)
    raw = Path(raw_text)
    if "\\" in raw_text or raw.is_absolute() or ".." in raw.parts or not raw.parts:
        raise BundleWriteError(f"unsafe bundle-relative path: {path}")
    normalized = raw.as_posix()
    if (
        normalized in {"", "."}
        or normalized.startswith("../")
        or "//" in raw_text
        or normalized != raw_text
    ):
        raise BundleWriteError(f"unsafe bundle-relative path: {path}")
    return normalized


def _json_text(value: BaseModel | Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_exclusive(path: Path, text: str) -> None:
    """Create a text payload without ever replacing an existing filesystem entry."""

    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise BundleWriteError(f"bundle payload already exists: {path.name}") from exc


class ResultBundleWriter:
    """Write an immutable result bundle into a previously absent or empty directory."""

    def __init__(self, output_dir: str | Path) -> None:
        self.root = Path(output_dir)
        if self.root.is_symlink():
            raise BundleWriteError(f"bundle path must not be a symlink: {self.root}")
        if self.root.exists() and not self.root.is_dir():
            raise BundleWriteError(f"bundle path exists and is not a directory: {self.root}")
        if self.root.exists() and any(self.root.iterdir()):
            raise BundleWriteError(f"bundle directory is not empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        self._payload_paths: set[str] = set()
        self._finalized = False

    def _target(self, relative_path: str | Path) -> tuple[str, Path]:
        if self._finalized:
            raise BundleWriteError("bundle is already finalized")
        normalized = _safe_relative_path(relative_path)
        if normalized in {"manifest.json", "checksums.sha256"}:
            raise BundleWriteError(f"{normalized} is reserved for bundle finalization")
        target = self.root / normalized
        if target.exists():
            raise BundleWriteError(f"bundle payload already exists: {normalized}")
        target.parent.mkdir(parents=True, exist_ok=True)
        return normalized, target

    def write_text(self, relative_path: str | Path, text: str) -> None:
        """Write UTF-8 text with normalized LF newlines."""

        normalized, target = self._target(relative_path)
        _write_text_exclusive(target, text)
        self._payload_paths.add(normalized)

    def write_json(self, relative_path: str | Path, value: BaseModel | Any) -> None:
        """Write deterministic human-readable JSON."""

        self.write_text(relative_path, _json_text(value))

    def copy_file(self, relative_path: str | Path, source: str | Path) -> None:
        """Copy an existing regular file into the bundle without following directory semantics."""

        normalized, target = self._target(relative_path)
        source_path = Path(source)
        if not source_path.is_file() or source_path.is_symlink():
            raise BundleWriteError(f"source is not a regular file: {source_path}")
        try:
            with source_path.open("rb") as source_handle, target.open("xb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle)
        except FileExistsError as exc:
            raise BundleWriteError(f"bundle payload already exists: {normalized}") from exc
        self._payload_paths.add(normalized)

    def finalize(self, core: ResultManifestCore) -> ResultManifest:
        """Write the manifest and checksums and prevent further writes."""

        if self._finalized:
            raise BundleWriteError("bundle is already finalized")
        inventory = tuple(sorted({*self._payload_paths, "manifest.json"}))
        manifest = ResultManifest(**core.model_dump(), file_inventory=inventory)
        manifest_path = self.root / "manifest.json"
        _write_text_exclusive(manifest_path, _json_text(manifest))

        checksum_lines = []
        for relative_path in inventory:
            checksum_lines.append(f"{_sha256_file(self.root / relative_path)}  {relative_path}\n")
        _write_text_exclusive(self.root / "checksums.sha256", "".join(checksum_lines))
        self._finalized = True
        return manifest
