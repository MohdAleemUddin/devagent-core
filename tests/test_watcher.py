import hashlib
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services import watcher


class FakeTimer:
    def __init__(self, _interval, callback, args=()):
        self.callback = callback
        self.args = args
        self.cancelled = False
        self.daemon = False

    def start(self):
        return None

    def cancel(self):
        self.cancelled = True


def test_handler_filters_non_markdown_events(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher.threading, "Timer", FakeTimer)
    handler = watcher.DocSyncHandler()
    try:
        handler.on_created(
            SimpleNamespace(is_directory=False, src_path=str(tmp_path / "notes.txt"))
        )
        assert handler._pending == {}

        doc = tmp_path / "guide.md"
        handler.on_created(
            SimpleNamespace(is_directory=False, src_path=str(doc))
        )
        assert doc in handler._pending
        assert handler._pending[doc][0] == 1
    finally:
        handler.stop()


def test_handler_debounces_and_skips_unchanged_content(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher.threading, "Timer", FakeTimer)
    doc = tmp_path / "guide.md"
    doc.write_text("# Guide", encoding="utf-8")
    handler = watcher.DocSyncHandler()
    ingest = AsyncMock()
    monkeypatch.setattr("app.services.rag.ingest_document_file", ingest)
    try:
        handler.on_created(
            SimpleNamespace(is_directory=False, src_path=str(doc))
        )
        generation, timer = handler._pending[doc]
        assert generation == 1
        handler.on_modified(
            SimpleNamespace(is_directory=False, src_path=str(doc))
        )
        assert timer.cancelled
        generation, _ = handler._pending[doc]
        assert generation == 2

        handler._process_change(doc, generation)
        ingest.assert_awaited_once_with(doc)
        assert handler._file_hashes[doc] == hashlib.sha256(
            b"# Guide"
        ).hexdigest()

        handler.on_modified(
            SimpleNamespace(is_directory=False, src_path=str(doc))
        )
        generation, _ = handler._pending[doc]
        handler._process_change(doc, generation)
        assert ingest.await_count == 1
    finally:
        handler.stop()


def test_handler_logs_ingestion_errors_without_marking_file_synced(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(watcher.threading, "Timer", FakeTimer)
    doc = tmp_path / "guide.md"
    doc.write_text("# Guide", encoding="utf-8")
    handler = watcher.DocSyncHandler()

    async def fail_ingestion(_path):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.services.rag.ingest_document_file", fail_ingestion)
    try:
        handler.on_created(
            SimpleNamespace(is_directory=False, src_path=str(doc))
        )
        generation, _ = handler._pending[doc]
        handler._process_change(doc, generation)

        assert "Failed to synchronize document" in caplog.text
        assert doc not in handler._file_hashes
    finally:
        handler.stop()


def test_handler_ignores_deleted_file(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher.threading, "Timer", FakeTimer)
    handler = watcher.DocSyncHandler()
    try:
        missing = tmp_path / "deleted.md"
        handler.on_created(
            SimpleNamespace(is_directory=False, src_path=str(missing))
        )
        generation, _ = handler._pending[missing]
        handler._process_change(missing, generation)

        assert missing not in handler._file_hashes
    finally:
        handler.stop()
