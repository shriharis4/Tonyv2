"""
Tests for the new Workstream 3 coverage tools: document authoring/editing,
PowerPoint, file system operations, and email configuration handling.

All file operations use pytest's tmp_path fixture — nothing here ever
touches the user's real Documents/Downloads/Desktop folders.
"""

import os

import pytest

from Tools.document_writer import write_document, edit_existing_file
from Tools.file_ops import (
    rename_file_or_folder,
    delete_file_or_folder,
    search_files_by_content,
    zip_paths,
    unzip_archive,
)
from Tools.send_email import send_email
from Tools.tool_result import is_failure


@pytest.mark.asyncio
async def test_write_document_text(tmp_path):
    target = tmp_path / "notes.txt"
    result = await write_document._func(app="text", path=str(target), content="Hello world")
    assert not is_failure(result)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Hello world"


@pytest.mark.asyncio
async def test_write_document_word(tmp_path):
    pytest.importorskip("docx")
    target = tmp_path / "summary.docx"
    result = await write_document._func(
        app="word", path=str(target),
        content="Renewable energy is important.\n\nIt reduces emissions.",
    )
    assert not is_failure(result)
    assert target.exists()

    from docx import Document
    doc = Document(str(target))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Renewable energy" in text


@pytest.mark.asyncio
async def test_write_document_rejects_empty_content(tmp_path):
    result = await write_document._func(app="text", path=str(tmp_path / "x.txt"), content="")
    assert is_failure(result)


@pytest.mark.asyncio
async def test_edit_existing_file_find_replace(tmp_path):
    target = tmp_path / "resume.txt"
    target.write_text("Name: Someone\nPhone: 555-0000", encoding="utf-8")

    result = await edit_existing_file._func(
        path=str(target), operation="find_replace", detail="555-0000=>555-0100"
    )
    assert not is_failure(result)
    assert "555-0100" in target.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_edit_existing_file_append(tmp_path):
    target = tmp_path / "log.txt"
    target.write_text("line1", encoding="utf-8")
    result = await edit_existing_file._func(path=str(target), operation="append", detail="line2")
    assert not is_failure(result)
    assert "line2" in target.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_edit_existing_file_missing_file_returns_clear_error(tmp_path):
    result = await edit_existing_file._func(
        path=str(tmp_path / "does_not_exist.txt"), operation="append", detail="x"
    )
    assert is_failure(result)


@pytest.mark.asyncio
async def test_delete_file_requires_confirmation(tmp_path):
    target = tmp_path / "throwaway.txt"
    target.write_text("data", encoding="utf-8")

    # Without confirm=True, nothing should be deleted.
    result = await delete_file_or_folder._func(path=str(target), confirm=False)
    assert is_failure(result)  # treated as a "needs confirmation" response
    assert target.exists()

    # With confirm=True, it proceeds.
    result2 = await delete_file_or_folder._func(path=str(target), confirm=True)
    assert not is_failure(result2)
    assert not target.exists()


@pytest.mark.asyncio
async def test_rename_file(tmp_path):
    target = tmp_path / "old_name.txt"
    target.write_text("data", encoding="utf-8")
    result = await rename_file_or_folder._func(path=str(target), new_name="new_name.txt")
    assert not is_failure(result)
    assert (tmp_path / "new_name.txt").exists()
    assert not target.exists()


@pytest.mark.asyncio
async def test_search_files_by_content(tmp_path, monkeypatch):
    import Tools.file_ops as file_ops_module
    monkeypatch.setattr(file_ops_module, "COMMON_DIRS", [str(tmp_path)])

    (tmp_path / "a.txt").write_text("the quick brown fox", encoding="utf-8")
    (tmp_path / "b.txt").write_text("nothing relevant here", encoding="utf-8")

    result = await search_files_by_content._func(query="quick brown", folder=str(tmp_path))
    assert not is_failure(result)
    assert "a.txt" in result


@pytest.mark.asyncio
async def test_zip_and_unzip_roundtrip(tmp_path):
    src = tmp_path / "data.txt"
    src.write_text("archived content", encoding="utf-8")
    zip_path = tmp_path / "archive.zip"

    zip_result = await zip_paths._func(paths=str(src), output_zip=str(zip_path))
    assert not is_failure(zip_result)
    assert zip_path.exists()

    extract_dir = tmp_path / "extracted"
    unzip_result = await unzip_archive._func(zip_path=str(zip_path), destination_folder=str(extract_dir))
    assert not is_failure(unzip_result)
    assert (extract_dir / "data.txt").read_text(encoding="utf-8") == "archived content"


@pytest.mark.asyncio
async def test_send_email_not_configured_returns_clear_message(monkeypatch):
    """When SMTP env vars are absent, send_email must return a clear
    'not configured' message — never a silent no-op or a crash."""
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    result = await send_email._func(to="someone@example.com", subject="Hi", message="Test")
    assert is_failure(result)
    assert "configured" in result.lower()


@pytest.mark.asyncio
async def test_send_email_rejects_invalid_address():
    result = await send_email._func(to="not-an-email", subject="Hi", message="Test")
    assert is_failure(result)
