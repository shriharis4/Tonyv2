"""
General document authoring and editing on real files on disk.

Closes the coverage gap where only Notepad had first-class write support.
Supports Word (.docx via python-docx), Markdown, and plain text creation,
plus find/replace, append, and insert-at-line editing of existing files.
"""

from __future__ import annotations

import asyncio
import os
from typing import Literal, Optional

from livekit.agents import function_tool

from Tools.tool_result import ok, fail

DEFAULT_DOC_DIR = os.path.join(os.path.expanduser("~"), "Documents")


def _resolve_path(path: str, format: str) -> str:
    """Resolve a user-given path/filename to an absolute path, defaulting to
    the Documents folder and adding the correct extension if missing."""
    path = os.path.expandvars(os.path.expanduser((path or "").strip()))
    if not os.path.isabs(path):
        path = os.path.join(DEFAULT_DOC_DIR, path)

    ext_map = {"word": ".docx", "markdown": ".md", "text": ".txt"}
    wanted_ext = ext_map.get(format, ".txt")
    root, ext = os.path.splitext(path)
    if ext.lower() not in (".docx", ".md", ".txt"):
        path = root + wanted_ext
    return path


def _write_docx(path: str, content: str) -> None:
    from docx import Document

    doc = Document()
    for para in content.split("\n\n"):
        doc.add_paragraph(para.strip())
    doc.save(path)


@function_tool()
async def write_document(
    app: Literal["word", "markdown", "text"],
    path: str,
    content: str,
    format: Optional[Literal["word", "markdown", "text"]] = None,
) -> str:
    """
    Author a real document on disk — not just typing into whatever window
    has focus.

    Args:
        app: Target authoring format/app: "word" (.docx), "markdown" (.md),
            or "text" (.txt).
        path: File name or path. Relative names are created under the
            user's Documents folder. Extension is added automatically if
            omitted.
        content: The document body. Paragraphs are separated by blank lines.
        format: Optional override for the output format; defaults to `app`.

    Returns:
        Structured success/failure string with the final file path.
    """
    fmt = format or app
    if fmt not in ("word", "markdown", "text"):
        return fail(f"Unsupported format '{fmt}'. Use word, markdown, or text.")
    if not content or not content.strip():
        return fail("No content provided to write.")

    try:
        final_path = _resolve_path(path, fmt)
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        loop = asyncio.get_running_loop()

        if fmt == "word":
            await loop.run_in_executor(None, _write_docx, final_path, content)
        else:
            def _write_plain():
                with open(final_path, "w", encoding="utf-8") as f:
                    f.write(content)
            await loop.run_in_executor(None, _write_plain)

        return ok(f"Document created at {final_path}", detail=f"format={fmt}")
    except ImportError:
        return fail(
            "python-docx is required for Word document authoring.",
            detail="pip install python-docx",
        )
    except Exception as e:
        return fail("Failed to write document", detail=str(e))


def _find_target_file(path: str) -> Optional[str]:
    """Resolve a loosely specified path to an existing file, searching
    common folders by fuzzy filename match if the exact path doesn't exist."""
    expanded = os.path.expandvars(os.path.expanduser((path or "").strip()))
    if os.path.isfile(expanded):
        return expanded

    search_dirs = [
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
    ]
    needle = os.path.basename(expanded).lower()
    if not needle:
        return None
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            if root.count(os.sep) - d.count(os.sep) > 1:
                continue
            for f in files:
                if needle in f.lower():
                    return os.path.join(root, f)
    return None


def _edit_docx(path: str, operation: str, detail: str) -> str:
    from docx import Document

    doc = Document(path)
    if operation == "find_replace":
        find, _, replace = detail.partition("=>")
        find, replace = find.strip(), replace.strip()
        count = 0
        for para in doc.paragraphs:
            if find in para.text:
                for run in para.runs:
                    if find in run.text:
                        run.text = run.text.replace(find, replace)
                        count += 1
                if find in para.text and count == 0:
                    # Fallback: replace across the whole paragraph text
                    para.text = para.text.replace(find, replace)
                    count += 1
        doc.save(path)
        return f"Replaced {count} occurrence(s) of '{find}' with '{replace}'"
    elif operation == "append":
        doc.add_paragraph(detail)
        doc.save(path)
        return "Appended text to document"
    elif operation == "insert_at_line":
        line_no_str, _, text = detail.partition("=>")
        line_no = int(line_no_str.strip())
        # python-docx has no native insert-before; rebuild paragraph order.
        paragraphs_text = [p.text for p in doc.paragraphs]
        paragraphs_text.insert(max(0, min(line_no, len(paragraphs_text))), text.strip())
        new_doc = Document()
        for t in paragraphs_text:
            new_doc.add_paragraph(t)
        new_doc.save(path)
        return f"Inserted text at line {line_no}"
    else:
        raise ValueError(f"Unknown operation '{operation}'")


def _edit_text_file(path: str, operation: str, detail: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    if operation == "find_replace":
        find, _, replace = detail.partition("=>")
        find, replace = find.strip(), replace.strip()
        text = "\n".join(lines)
        count = text.count(find)
        text = text.replace(find, replace)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return f"Replaced {count} occurrence(s) of '{find}' with '{replace}'"
    elif operation == "append":
        with open(path, "a", encoding="utf-8") as f:
            f.write(("\n" if lines else "") + detail)
        return "Appended text to file"
    elif operation == "insert_at_line":
        line_no_str, _, text = detail.partition("=>")
        line_no = int(line_no_str.strip())
        lines.insert(max(0, min(line_no, len(lines))), text)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return f"Inserted text at line {line_no}"
    else:
        raise ValueError(f"Unknown operation '{operation}'")


@function_tool()
async def edit_existing_file(
    path: str,
    operation: Literal["find_replace", "append", "insert_at_line"],
    detail: str,
) -> str:
    """
    Edit a real file already saved on disk — find/replace, append, or
    insert-at-line. Supports .docx, .md, and .txt files.

    Args:
        path: File name or path. Fuzzy-matched against Documents/Downloads/
            Desktop if not an exact existing path.
        operation: "find_replace" (detail format "OLD=>NEW"), "append"
            (detail is the text to add), or "insert_at_line" (detail format
            "LINE_NUMBER=>TEXT", 0-indexed).
        detail: Operation-specific payload, see `operation` above.

    Returns:
        Structured success/failure string describing what changed.
    """
    if not detail or not detail.strip():
        return fail("No edit detail provided.")

    target = _find_target_file(path)
    if not target:
        return fail(f"Could not find a file matching '{path}'.")

    ext = os.path.splitext(target)[1].lower()
    if ext not in (".docx", ".md", ".txt"):
        return fail(f"Unsupported file type '{ext}' for editing.")

    try:
        loop = asyncio.get_running_loop()
        if ext == ".docx":
            msg = await loop.run_in_executor(None, _edit_docx, target, operation, detail)
        else:
            msg = await loop.run_in_executor(None, _edit_text_file, target, operation, detail)
        return ok(msg, detail=f"file={target}")
    except ValueError as e:
        return fail(str(e))
    except ImportError:
        return fail(
            "python-docx is required to edit Word documents.",
            detail="pip install python-docx",
        )
    except Exception as e:
        return fail("Failed to edit file", detail=str(e))
