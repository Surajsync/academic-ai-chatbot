import csv
import re
import unittest
from collections import Counter
from pathlib import Path


class FAQDataQualityTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.faq_path = self.repo_root / "backend" / "data" / "faq_optimized.csv"
        self.data_dir = self.repo_root / "backend" / "data"

    def test_faq_csv_exists_and_has_expected_headers(self):
        self.assertTrue(self.faq_path.exists(), f"Missing FAQ file: {self.faq_path}")
        with self.faq_path.open("r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            self.assertEqual(
                reader.fieldnames,
                ["question", "answer", "keywords"],
                "FAQ headers must be exactly: question, answer, keywords",
            )

    def test_faq_rows_are_non_empty(self):
        with self.faq_path.open("r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            rows = list(reader)

        self.assertGreater(len(rows), 0, "FAQ dataset must not be empty")

        for index, row in enumerate(rows, start=2):
            question = (row.get("question") or "").strip()
            answer = (row.get("answer") or "").strip()
            self.assertTrue(question, f"Row {index}: question is empty")
            self.assertTrue(answer, f"Row {index}: answer is empty")

    def test_no_duplicate_normalized_questions(self):
        with self.faq_path.open("r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            normalized_questions = [
                re.sub(r"[^a-z0-9 ]", "", (row["question"] or "").strip().lower())
                for row in reader
            ]

        duplicates = [
            question
            for question, count in Counter(normalized_questions).items()
            if question and count > 1
        ]
        self.assertEqual([], duplicates, f"Duplicate FAQ questions found: {duplicates}")

    def test_no_editor_lock_files_in_data_directory(self):
        lock_files = sorted(path.name for path in self.data_dir.glob('.~lock.*'))
        self.assertEqual([], lock_files, f"Remove temporary lock files from backend/data: {lock_files}")


if __name__ == "__main__":
    unittest.main()
