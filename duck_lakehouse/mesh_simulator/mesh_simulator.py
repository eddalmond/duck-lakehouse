#!/usr/bin/env python3
"""
MESH Simulator - Local file-based simulation of NHS MESH

(Message Exchange for Social Care and Health)

Simulates the MESH workflow:
  1. Watch inbox/ for new .csv files from supplier systems
  2. Move to processing/ for ingestion
  3. Move to archive/ after successful processing

Mirrors the terraform-aws-mesh-client serverless pattern where
S3 events trigger Lambda processing of inbound messages.
"""

import hashlib
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MESH] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class MESHMessage:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.filename = filepath.name
        self.size = filepath.stat().st_size
        self.checksum = self._compute_checksum()
        self.received_at = datetime.utcnow().isoformat()
        self.message_id = hashlib.sha256(
            f"{self.filename}{self.received_at}".encode()
        ).hexdigest()[:16]

    def _compute_checksum(self) -> str:
        sha256 = hashlib.sha256()
        with open(self.filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def metadata(self) -> dict:
        return {
            "message_id": self.message_id,
            "filename": self.filename,
            "size": self.size,
            "checksum": self.checksum,
            "received_at": self.received_at,
        }


class MESHSimulator:
    def __init__(
        self,
        base_dir: str = None,
        poll_interval: float = 2.0,
    ):
        if base_dir is None:
            pkg_dir = Path(__file__).resolve().parent.parent
            base_dir = str(pkg_dir / "mesh_simulator")
        self.base_dir = Path(base_dir)
        self.inbox_dir = self.base_dir / "inbox"
        self.processing_dir = self.base_dir / "processing"
        self.archive_dir = self.base_dir / "archive"
        self.log_dir = self.base_dir / "logs"
        self.poll_interval = poll_interval
        self._running = False

        for d in [self.inbox_dir, self.processing_dir, self.archive_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def scan_inbox(self) -> list:
        files = list(self.inbox_dir.glob("*.csv"))
        return [MESHMessage(f) for f in files]

    def move_to_processing(self, message: MESHMessage) -> Path:
        dest = self.processing_dir / message.filename
        shutil.move(str(message.filepath), str(dest))
        logger.info("Moved %s -> processing/", message.filename)
        self._log_event("move_to_processing", message)
        return dest

    def move_to_archive(self, message: MESHMessage) -> Path:
        src = self.processing_dir / message.filename
        if not src.exists():
            raise FileNotFoundError(f"File not in processing: {message.filename}")
        dest = self.archive_dir / message.filename
        shutil.move(str(src), str(dest))
        logger.info("Moved %s -> archive/", message.filename)
        self._log_event("archive", message)
        return dest

    def process_message(self, message: MESHMessage) -> Optional[Path]:
        try:
            self.move_to_processing(message)
            logger.info("Processing %s (%d bytes)", message.filename, message.size)
            time.sleep(0.1)
            archive_path = self.move_to_archive(message)
            logger.info("Completed %s", message.filename)
            return archive_path
        except Exception as e:
            logger.error("Failed processing %s: %s", message.filename, e)
            self._log_event("error", message, error=str(e))
            return None

    def process_all(self) -> list:
        messages = self.scan_inbox()
        logger.info("Found %d files in inbox", len(messages))
        results = []
        for msg in messages:
            result = self.process_message(msg)
            results.append((msg.filename, result is not None))
        return results

    def run(self, max_iterations: Optional[int] = None):
        self._running = True
        iteration = 0
        logger.info("MESH Simulator started (polling every %.1fs)", self.poll_interval)

        while self._running:
            messages = self.scan_inbox()
            if messages:
                logger.info("Processing %d inbound messages", len(messages))
                for msg in messages:
                    self.process_message(msg)
            else:
                logger.debug("Inbox empty")

            iteration += 1
            if max_iterations and iteration >= max_iterations:
                break

            time.sleep(self.poll_interval)

        logger.info("MESH Simulator stopped")

    def stop(self):
        self._running = False

    def _log_event(self, event_type: str, message: MESHMessage, **extra):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            **message.metadata(),
            **extra,
        }
        log_file = self.log_dir / f"mesh_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MESH Simulator")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory for MESH directories (default: package/mesh_simulator)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between inbox scans",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process inbox once and exit",
    )
    args = parser.parse_args()

    sim = MESHSimulator(base_dir=args.base_dir, poll_interval=args.poll_interval)

    if args.once:
        results = sim.process_all()
        for filename, success in results:
            status = "OK" if success else "FAIL"
            print(f"  [{status}] {filename}")
    else:
        try:
            sim.run()
        except KeyboardInterrupt:
            sim.stop()


if __name__ == "__main__":
    main()
