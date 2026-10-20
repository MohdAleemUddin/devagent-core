import asyncio
import hashlib
import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("DevAgentWatcher")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"


class DocSyncHandler(FileSystemEventHandler):
    """Debounces document updates and runs ingestion on one persistent event loop."""

    def __init__(self):
        super().__init__()
        self.cooldown = 6.0
        self._condition = threading.Condition()
        self._pending: dict[Path, tuple[int, threading.Timer]] = {}
        self._generations: dict[Path, int] = {}
        self._file_hashes: dict[Path, str] = {}
        self._active_ingestions = 0
        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(
            target=self._run_event_loop,
            name="document-ingestion-loop",
            daemon=True,
        )
        self._loop_thread.start()
        self._loop_ready.wait()

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending_tasks = asyncio.all_tasks(self._loop)
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                self._loop.run_until_complete(
                    asyncio.gather(*pending_tasks, return_exceptions=True)
                )
            self._loop.close()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".md"):
            self._schedule_change(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".md"):
            self._schedule_change(Path(event.src_path))

    def _schedule_change(self, file_path: Path):
        with self._condition:
            pending = self._pending.get(file_path)
            if pending:
                _, previous_timer = pending
                previous_timer.cancel()

            generation = self._generations.get(file_path, 0) + 1
            self._generations[file_path] = generation
            timer = threading.Timer(
                self.cooldown,
                self._process_change,
                args=(file_path, generation),
            )
            timer.daemon = True
            self._pending[file_path] = (generation, timer)
            timer.start()

    def _process_change(self, file_path: Path, generation: int):
        with self._condition:
            pending = self._pending.get(file_path)
            if pending is None or pending[0] != generation:
                return
            self._pending.pop(file_path)
            self._active_ingestions += 1

        try:
            if not file_path.exists():
                return

            content = file_path.read_text(encoding="utf-8")
            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            with self._condition:
                if self._file_hashes.get(file_path) == file_hash:
                    return

            logger.info("Document update detected: %s. Syncing...", file_path.name)

            from app.services.rag import ingest_document_file

            future = asyncio.run_coroutine_threadsafe(
                ingest_document_file(file_path),
                self._loop,
            )
            future.result()

            with self._condition:
                self._file_hashes[file_path] = file_hash
            logger.info("Successfully synchronized %s", file_path.name)
        except Exception:
            logger.exception("Failed to synchronize document %s", file_path.name)
        finally:
            with self._condition:
                self._active_ingestions -= 1
                self._condition.notify_all()

    def stop(self):
        with self._condition:
            for _, timer in self._pending.values():
                timer.cancel()
            self._pending.clear()
            while self._active_ingestions:
                self._condition.wait()

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join()


def start_file_watcher():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    event_handler = DocSyncHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(DOCS_DIR), recursive=False)

    try:
        observer.start()
        logger.info("Document watcher active. Monitoring: %s", DOCS_DIR)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Document watcher stopping.")
    finally:
        observer.stop()
        observer.join()
        event_handler.stop()


if __name__ == "__main__":
    start_file_watcher()
