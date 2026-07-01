import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "backend" / "scripts" / "quickstart.py"


class QuickstartScriptTests(unittest.TestCase):
    def test_dry_run_lists_bundled_demo_assets(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("data\\samples\\demo", result.stdout)
        self.assertIn("contract_notice.md", result.stdout)
        self.assertIn("meeting_notes.md", result.stdout)
        self.assertIn("tech_manual.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
