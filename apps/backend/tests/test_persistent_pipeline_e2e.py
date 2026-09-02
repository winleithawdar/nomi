from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PersistentPipelineEndToEndTest(unittest.TestCase):
    def test_database_to_webhook_to_delivered_alert(self) -> None:
        backend_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "pipeline.db"
            environment = os.environ.copy()
            environment.update(
                {
                    "DATABASE_URL": f"sqlite:///{database_path}",
                    "NOMI_DATA_MODE": "database",
                    "NOMI_MESSAGING_PROVIDER": "mock",
                    "WHATSAPP_APP_SECRET": "test-secret",
                }
            )
            completed = subprocess.run(
                [sys.executable, "tests/_database_pipeline_scenario.py"],
                cwd=backend_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
