from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from coach_garmin.coach_tools import LocalCoachToolkit
from coach_garmin.pwa_service import _build_reset_cache_page
from coach_garmin.storage import write_json
from coach_garmin.text_encoding import repair_mojibake_text, repair_text_tree


class TextEncodingTest(unittest.TestCase):
    def test_repair_mojibake_text_repairs_french_strings(self) -> None:
        self.assertEqual(repair_mojibake_text("DonnÃ©es locales prÃªtes"), "Données locales prêtes")
        self.assertEqual(repair_mojibake_text("Analyse: prÃªte"), "Analyse: prête")

    def test_repair_text_tree_repairs_nested_payloads(self) -> None:
        payload = {
            "title": "RÃ©sumÃ©",
            "nested": ["DonnÃ©es", {"state": "prÃªte"}],
        }
        repaired = repair_text_tree(payload)
        self.assertEqual(repaired["title"], "Résumé")
        self.assertEqual(repaired["nested"][0], "Données")
        self.assertEqual(repaired["nested"][1]["state"], "prête")

    def test_write_json_emits_readable_utf8(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.json"
            write_json(path, {"message": "Données locales prêtes"})
            raw = path.read_text(encoding="utf-8")
            self.assertIn("Données locales prêtes", raw)
            self.assertEqual(json.loads(raw)["message"], "Données locales prêtes")

    def test_local_coach_toolkit_repairs_goal_profile_on_read(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            report_dir = data_dir / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            goal_path = report_dir / "goal_profile.json"
            goal_path.write_text('{"goal_text": "Je veux courir un 10 km en prÃªte forme"}\n', encoding="utf-8")
            toolkit = LocalCoachToolkit(data_dir=data_dir)
            payload = toolkit.goals()
            self.assertEqual(payload["goal_profile"]["goal_text"], "Je veux courir un 10 km en prête forme")

    def test_reset_cache_page_contains_readable_french_text(self) -> None:
        html = _build_reset_cache_page("/?v=test", "20260414")
        self.assertIn("Démarrage de la purge", html)
        self.assertIn("Cache purgé", html)
        self.assertIn("après ça", html)

    def test_active_source_files_do_not_contain_raw_mojibake(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_roots = [root / "coach_garmin", root / "web"]
        excluded_files = {
            root / "coach_garmin" / "text_encoding.py",
            Path(__file__).resolve(),
        }
        markers = ("Ãƒ", "Ã‚", "Ã©", "Ã¨", "Ãª", "Ã§", "Ã ", "â€™", "â€”", "Â·")
        offenders: list[str] = []
        for source_root in source_roots:
            for path in source_root.rglob("*"):
                if path in excluded_files or path.suffix.lower() not in {".py", ".js", ".html", ".css"}:
                    continue
                for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    if "repairMojibakeText" in line or "mojibake" in line.lower():
                        continue
                    if any(marker in line for marker in markers):
                        offenders.append(f"{path.relative_to(root)}:{line_no}: {line.strip()}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
