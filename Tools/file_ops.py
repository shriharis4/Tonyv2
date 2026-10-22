"""
File system operations: rename, move, copy, delete (with confirmation),
content search, zip/unzip, and batch rename across common folders.

Safety: `delete_file_or_folder` requires an explicit `confirm=True` flag —
this mirrors the system_power_action confirmation discipline so destructive
filesystem actions never execute on a single ambiguous utterance.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import shutil
import zipfile
from typing import List, Optional

from livekit.agents import function_tool

from Tools.tool_result import ok, fail

COMMON_DIRS = [
    os.path.join(os.path.expanduser("~"), "Documents"),
    os.path.join(os.path.expanduser("~"), "Downloads"),
    os.path.join(os.path.expanduser("~"), "Desktop"),
]


def _resolve_existing_path(path: str) -> Optional[str]:
    expanded = os.path.expandvars(os.path.expanduser((path or "").strip()))
    if os.path.exists(expanded):
        return expanded
    needle = os.path.basename(expanded).lower()
    if not needle:
        return None
    for d in COMMON_DIRS:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            if root.count(os.sep) - d.count(os.sep) > 1:
                continue
            for name in files + dirs:
                if needle in name.lower():
                    return os.path.join(root, name)
    return None


@function_tool()
async def rename_file_or_folder(path: str, new_name: str) -> str:
    """
    Rename a file or folder in place.

    Args:
        path: Existing file/folder path or fuzzy name (searched in
            Documents/Downloads/Desktop if not an exact path).
        new_name: New file/folder name (not a full path — kept in the same
            parent directory).

    Returns:
        Structured success/failure string with the new path.
    """
    target = _resolve_existing_path(path)
    if not target:
        return fail(f"Could not find '{path}'.")
    if not new_name or any(c in new_name for c in r'\/:*?"<>|'):
        return fail("Invalid new name.")

    try:
        new_path = os.path.join(os.path.dirname(target), new_name)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, os.rename, target, new_path)
        return ok(f"Renamed to {new_path}")
    except Exception as e:
        return fail("Rename failed", detail=str(e))


@function_tool()
async def move_file_or_folder(path: str, destination_folder: str) -> str:
    """
    Move a file or folder into a destination folder.

    Args:
        path: Existing file/folder path or fuzzy name.
        destination_folder: Target folder path. Created if it doesn't exist.

    Returns:
        Structured success/failure string with the new path.
    """
    target = _resolve_existing_path(path)
    if not target:
        return fail(f"Could not find '{path}'.")

    try:
        dest_dir = os.path.expandvars(os.path.expanduser(destination_folder.strip()))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: os.makedirs(dest_dir, exist_ok=True))
        new_path = os.path.join(dest_dir, os.path.basename(target))
        await loop.run_in_executor(None, shutil.move, target, new_path)
        return ok(f"Moved to {new_path}")
    except Exception as e:
        return fail("Move failed", detail=str(e))


@function_tool()
async def copy_file_or_folder(path: str, destination_folder: str) -> str:
    """
    Copy a file or folder into a destination folder, preserving the
    original.

    Args:
        path: Existing file/folder path or fuzzy name.
        destination_folder: Target folder path. Created if it doesn't exist.

    Returns:
        Structured success/failure string with the new path.
    """
    target = _resolve_existing_path(path)
    if not target:
        return fail(f"Could not find '{path}'.")

    try:
        dest_dir = os.path.expandvars(os.path.expanduser(destination_folder.strip()))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: os.makedirs(dest_dir, exist_ok=True))
        new_path = os.path.join(dest_dir, os.path.basename(target))

        def _copy():
            if os.path.isdir(target):
                shutil.copytree(target, new_path)
            else:
                shutil.copy2(target, new_path)

        await loop.run_in_executor(None, _copy)
        return ok(f"Copied to {new_path}")
    except Exception as e:
        return fail("Copy failed", detail=str(e))


@function_tool()
async def delete_file_or_folder(path: str, confirm: bool = False) -> str:
    """
    Delete a file or folder. REQUIRES explicit confirmation — this is a
    destructive, irreversible action (folders are removed recursively).

    Args:
        path: Existing file/folder path or fuzzy name.
        confirm: Must be True to actually delete. If False, returns the
            resolved target and asks the caller to confirm first; nothing
            is deleted.

    Returns:
        Structured success/failure string, or a confirmation prompt.
    """
    target = _resolve_existing_path(path)
    if not target:
        return fail(f"Could not find '{path}'.")

    if not confirm:
        kind = "folder" if os.path.isdir(target) else "file"
        return fail(
            f"Deletion requires confirmation. Found {kind}: {target}. "
            "Ask the user to confirm, then call again with confirm=True.",
        )

    try:
        loop = asyncio.get_running_loop()

        def _delete():
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)

        await loop.run_in_executor(None, _delete)
        return ok(f"Deleted {target}")
    except Exception as e:
        return fail("Delete failed", detail=str(e))


@function_tool()
async def search_files_by_content(query: str, folder: Optional[str] = None, file_pattern: str = "*.txt") -> str:
    """
    Search for a text query inside files' content (not just filename)
    across a folder (defaults to Documents/Downloads/Desktop).

    Args:
        query: Text to search for inside file contents (case-insensitive).
        folder: Optional specific folder to search. Defaults to common
            user folders if omitted.
        file_pattern: Glob pattern restricting which files are scanned,
            e.g. "*.txt", "*.md", "*.py". Defaults to "*.txt".

    Returns:
        Structured string listing matching files (up to 20), or a
        not-found message.
    """
    if not query or not query.strip():
        return fail("No search query provided.")

    search_dirs = [os.path.expandvars(os.path.expanduser(folder.strip()))] if folder else COMMON_DIRS
    matches: List[str] = []

    def _scan():
        needle = query.lower()
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for fname in fnmatch.filter(files, file_pattern):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            if needle in f.read().lower():
                                matches.append(fpath)
                    except Exception:
                        continue
                    if len(matches) >= 20:
                        return

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _scan)
        if not matches:
            return fail(f"No files matching '{file_pattern}' contain '{query}'.")
        listing = "\n".join(matches)
        return ok(f"Found {len(matches)} file(s) containing '{query}'", detail=listing)
    except Exception as e:
        return fail("Content search failed", detail=str(e))


@function_tool()
async def zip_paths(paths: str, output_zip: str) -> str:
    """
    Compress one or more files/folders into a .zip archive.

    Args:
        paths: Comma-separated list of file/folder paths or fuzzy names to
            include in the archive.
        output_zip: Destination .zip file path. Created under Documents if
            a relative name is given.

    Returns:
        Structured success/failure string with the archive path.
    """
    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    if not path_list:
        return fail("No paths provided to zip.")

    resolved = []
    for p in path_list:
        target = _resolve_existing_path(p)
        if not target:
            return fail(f"Could not find '{p}'.")
        resolved.append(target)

    out_path = os.path.expandvars(os.path.expanduser(output_zip.strip()))
    if not os.path.isabs(out_path):
        out_path = os.path.join(os.path.expanduser("~"), "Documents", out_path)
    if not out_path.lower().endswith(".zip"):
        out_path += ".zip"

    def _zip():
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for target in resolved:
                if os.path.isdir(target):
                    for root, _, files in os.walk(target):
                        for fname in files:
                            fpath = os.path.join(root, fname)
                            arcname = os.path.relpath(fpath, os.path.dirname(target))
                            zf.write(fpath, arcname)
                else:
                    zf.write(target, os.path.basename(target))

    try:
        loop = asyncio.get_running_loop()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        await loop.run_in_executor(None, _zip)
        return ok(f"Created archive {out_path}", detail=f"{len(resolved)} item(s)")
    except Exception as e:
        return fail("Zip failed", detail=str(e))


@function_tool()
async def unzip_archive(zip_path: str, destination_folder: Optional[str] = None) -> str:
    """
    Extract a .zip archive into a destination folder.

    Args:
        zip_path: Path or fuzzy name of the .zip file to extract.
        destination_folder: Target folder. Defaults to a folder named after
            the archive, next to the archive itself.

    Returns:
        Structured success/failure string with the extraction path.
    """
    target = _resolve_existing_path(zip_path)
    if not target or not target.lower().endswith(".zip"):
        return fail(f"Could not find a .zip archive matching '{zip_path}'.")

    dest = destination_folder or os.path.splitext(target)[0]
    dest = os.path.expandvars(os.path.expanduser(dest))

    def _unzip():
        with zipfile.ZipFile(target, "r") as zf:
            zf.extractall(dest)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _unzip)
        return ok(f"Extracted to {dest}")
    except Exception as e:
        return fail("Unzip failed", detail=str(e))


@function_tool()
async def batch_rename(folder: str, pattern: str, replacement: str) -> str:
    """
    Batch rename files in a folder by substring/pattern replacement in
    their file names (not file content).

    Args:
        folder: Folder containing files to rename.
        pattern: Substring to search for in each file name.
        replacement: Text to replace `pattern` with.

    Returns:
        Structured success/failure string listing how many files were
        renamed.
    """
    target_dir = os.path.expandvars(os.path.expanduser(folder.strip()))
    if not os.path.isdir(target_dir):
        return fail(f"Folder not found: {target_dir}")
    if not pattern:
        return fail("No pattern provided.")

    renamed = 0

    def _rename_all():
        nonlocal renamed
        for fname in os.listdir(target_dir):
            if pattern in fname:
                new_name = fname.replace(pattern, replacement)
                if new_name != fname:
                    os.rename(
                        os.path.join(target_dir, fname),
                        os.path.join(target_dir, new_name),
                    )
                    renamed += 1

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _rename_all)
        if renamed == 0:
            return fail(f"No files containing '{pattern}' found in {target_dir}.")
        return ok(f"Renamed {renamed} file(s) in {target_dir}")
    except Exception as e:
        return fail("Batch rename failed", detail=str(e))
