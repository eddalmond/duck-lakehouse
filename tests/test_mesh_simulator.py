import json
from pathlib import Path

import pytest

from duck_lakehouse.mesh_simulator.mesh_simulator import MESHMessage, MESHSimulator


class TestMESHMessage:
    def test_message_metadata(self, tmp_dir):
        filepath = tmp_dir / "test.csv"
        filepath.write_text("test,data\r\n1,2\r\n", encoding="utf-8")

        msg = MESHMessage(filepath)
        assert msg.filename == "test.csv"
        assert msg.size > 0
        assert msg.checksum
        assert msg.message_id
        assert msg.received_at

    def test_message_checksum_consistent(self, tmp_dir):
        filepath = tmp_dir / "test.csv"
        filepath.write_text("test,data\r\n1,2\r\n", encoding="utf-8")

        msg1 = MESHMessage(filepath)
        msg2 = MESHMessage(filepath)
        assert msg1.checksum == msg2.checksum

    def test_message_checksum_differs_for_content(self, tmp_dir):
        f1 = tmp_dir / "test1.csv"
        f2 = tmp_dir / "test2.csv"
        f1.write_text("content_a\r\n", encoding="utf-8")
        f2.write_text("content_b\r\n", encoding="utf-8")

        msg1 = MESHMessage(f1)
        msg2 = MESHMessage(f2)
        assert msg1.checksum != msg2.checksum

    def test_metadata_dict(self, tmp_dir):
        filepath = tmp_dir / "test.csv"
        filepath.write_text("test,data\r\n1,2\r\n", encoding="utf-8")

        msg = MESHMessage(filepath)
        meta = msg.metadata()
        assert "message_id" in meta
        assert "filename" in meta
        assert "size" in meta
        assert "checksum" in meta
        assert "received_at" in meta
        assert meta["filename"] == "test.csv"


class TestMESHSimulator:
    def test_init_creates_dirs(self, mesh_dirs):
        import tempfile
        base = Path(tempfile.mkdtemp())
        sim = MESHSimulator(base_dir=str(base))
        assert (base / "inbox").is_dir()
        assert (base / "processing").is_dir()
        assert (base / "archive").is_dir()
        assert (base / "logs").is_dir()

    def test_scan_inbox_empty(self, mesh_dirs):
        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        messages = sim.scan_inbox()
        assert messages == []

    def test_scan_inbox_with_files(self, mesh_dirs):
        (mesh_dirs["inbox"] / "test1.csv").write_text("data\r\n", encoding="utf-8")
        (mesh_dirs["inbox"] / "test2.csv").write_text("data\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        messages = sim.scan_inbox()
        assert len(messages) == 2
        names = {m.filename for m in messages}
        assert "test1.csv" in names
        assert "test2.csv" in names

    def test_move_to_processing(self, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        msg = MESHMessage(filepath)
        dest = sim.move_to_processing(msg)
        assert dest.exists()
        assert not filepath.exists()
        assert dest == mesh_dirs["processing"] / "test.csv"

    def test_move_to_archive(self, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        msg = MESHMessage(filepath)
        sim.move_to_processing(msg)
        dest = sim.move_to_archive(msg)
        assert dest.exists()
        assert dest == mesh_dirs["archive"] / "test.csv"

    def test_process_message(self, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        msg = MESHMessage(filepath)
        result = sim.process_message(msg)
        assert result is not None
        assert result.exists()
        assert (mesh_dirs["archive"] / "test.csv").exists()

    def test_process_all(self, mesh_dirs):
        for i in range(3):
            (mesh_dirs["inbox"] / f"test_{i}.csv").write_text(f"data_{i}\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        results = sim.process_all()
        assert len(results) == 3
        assert all(success for _, success in results)

    def test_log_events(self, mesh_dirs):
        filepath = mesh_dirs["inbox"] / "test.csv"
        filepath.write_text("data\r\n", encoding="utf-8")

        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        msg = MESHMessage(filepath)
        sim.process_message(msg)

        log_files = list(mesh_dirs["logs"].glob("*.jsonl"))
        assert len(log_files) >= 1

        log_content = log_files[0].read_text(encoding="utf-8")
        log_entries = [json.loads(line) for line in log_content.strip().split("\n") if line.strip()]
        assert any(e["event"] == "move_to_processing" for e in log_entries)
        assert any(e["event"] == "archive" for e in log_entries)

    def test_archive_not_found_raises(self, mesh_dirs):
        filepath = mesh_dirs["processing"] / "nonexistent.csv"
        filepath.write_text("data\r\n", encoding="utf-8")
        sim = MESHSimulator(base_dir=str(mesh_dirs["archive"].parent))
        msg = MESHMessage(filepath)
        filepath.unlink()
        with pytest.raises(FileNotFoundError):
            sim.move_to_archive(msg)