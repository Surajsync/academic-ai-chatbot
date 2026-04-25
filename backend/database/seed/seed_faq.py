import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from backend.database.database import SessionLocal
from backend.database.models import FAQ


@dataclass
class FAQRow:
    question: str
    answer: str
    keywords: str
    embedding: str | None = None
    is_active: bool = True


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = BACKEND_DIR / "data" / "faq_optimized.csv"


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _normalize_for_key(value: str) -> str:
    cleaned = _clean_spaces(value).lower()
    return re.sub(r"[^a-z0-9 ]", "", cleaned)


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y"}:
        return True
    if normalized in {"0", "false", "f", "no", "n"}:
        return False
    return default


def _normalize_keywords(raw_keywords: str, question: str) -> str:
    text = _clean_spaces(raw_keywords)
    if not text:
        # Fallback keywords from question for better FAQ retrieval.
        tokens = [token for token in _normalize_for_key(question).split() if len(token) > 2]
        return ", ".join(tokens[:8])

    parts = [part.strip().lower() for part in text.split(",") if part.strip()]
    seen = set()
    unique_parts = []
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        unique_parts.append(part)
    return ", ".join(unique_parts[:15])


def _normalize_embedding(raw_embedding: Any) -> str | None:
    if raw_embedding is None:
        return None
    if isinstance(raw_embedding, str):
        text = raw_embedding.strip()
        if not text:
            return None
        import json
        return [float(x) for x in json.loads(text)]
    if isinstance(raw_embedding, list):
        return [float(x) for x in raw_embedding]
    return None


def _is_low_quality(answer: str) -> bool:
    normalized = answer.lower()
    if len(answer) < 20:
        return True
    if normalized.startswith("source:"):
        return True
    if ".csv" in normalized or ".xls" in normalized:
        return True
    return False


def _dict_to_row(item: dict[str, Any]) -> tuple[FAQRow | None, str | None]:
    question = _clean_spaces(str(item.get("question") or item.get("keyword") or item.get("keywords") or ""))
    answer = _clean_spaces(str(item.get("answer") or item.get("response") or ""))
    keywords = _normalize_keywords(str(item.get("keywords") or item.get("keyword") or ""), question)
    is_active = _parse_bool(item.get("is_active"), default=True)

    if not question or not answer:
        return None, "missing-question-or-answer"
    if _is_low_quality(answer):
        return None, "low-quality-answer"

    return (
        FAQRow(
            question=question,
            answer=answer,
            keywords=keywords,
            is_active=is_active,
        ),
        None,
    )


def _count_rejected(rejected: dict[str, int], reason: str | None) -> None:
    if not reason:
        return
    rejected[reason] = rejected.get(reason, 0) + 1


def _read_csv_rows(source: Path) -> tuple[list[FAQRow], dict[str, int]]:
    rows: list[FAQRow] = []
    rejected: dict[str, int] = {}
    with source.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for item in reader:
            row, reason = _dict_to_row(item)
            if row:
                rows.append(row)
            else:
                _count_rejected(rejected, reason)
    return rows, rejected


def _read_json_rows(source: Path) -> tuple[list[FAQRow], dict[str, int]]:
    rows: list[FAQRow] = []
    rejected: dict[str, int] = {}
    with source.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if isinstance(payload, dict):
        payload = payload.get("data", [])

    if not isinstance(payload, list):
        raise ValueError("JSON FAQ source must be a list of objects")

    for item in payload:
        if not isinstance(item, dict):
            _count_rejected(rejected, "invalid-json-item")
            continue
        row, reason = _dict_to_row(item)
        if row:
            rows.append(row)
        else:
            _count_rejected(rejected, reason)
    return rows, rejected


def _load_rows(source: Path) -> tuple[list[FAQRow], dict[str, int]]:
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return _read_csv_rows(source)
    if suffix == ".json":
        return _read_json_rows(source)
    raise ValueError(f"Unsupported source format: {source.suffix}. Use CSV or JSON")


def _rows_to_dicts(rows: list[FAQRow]) -> list[dict[str, Any]]:
    return [
        {
            "question": row.question,
            "answer": row.answer,
            "keywords": row.keywords,
            "embedding": row.embedding,
            "is_active": row.is_active,
        }
        for row in rows
    ]


def _write_clean_rows(path: str, rows: list[FAQRow]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    suffix = output.suffix.lower()
    payload = _rows_to_dicts(rows)

    if suffix == ".json":
        with output.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, indent=2, ensure_ascii=True)
        return output

    if suffix == ".csv":
        with output.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(
                file_obj,
                fieldnames=["question", "answer", "keywords", "embedding", "is_active"],
            )
            writer.writeheader()
            writer.writerows(payload)
        return output

    raise ValueError("--clean-output must end with .csv or .json")


def _dedupe_rows(rows: list[FAQRow]) -> tuple[list[FAQRow], int]:
    unique: dict[str, FAQRow] = {}
    duplicates = 0

    for row in rows:
        key = _normalize_for_key(row.question)
        if not key:
            continue
        if key in unique:
            duplicates += 1
            # Keep latest row to make updates easier from newer files.
            unique[key] = row
        else:
            unique[key] = row

    return list(unique.values()), duplicates


def _build_embedding_model(enable_embeddings: bool):
    return None

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required when --embed-missing is used"
        ) from exc

    return SentenceTransformer("all-MiniLM-L6-v2")


def _upsert_faqs(
    mode: str,
    rows: list[FAQRow],
    dry_run: bool,
    deactivate_missing: bool,
    embed_missing: False,
) -> dict[str, int]:
    db = SessionLocal()
    stats = {
        "inserted": 0,
        "updated": 0,
        "deactivated": 0,
        "skipped": 0,
    }

    model = _build_embedding_model(embed_missing)

    try:
        existing_faqs = db.query(FAQ).all()
        existing_by_key: dict[str, FAQ] = {}
        for faq in existing_faqs:
            key = _normalize_for_key(faq.question or "")
            if key:
                existing_by_key[key] = faq

        incoming_keys = {_normalize_for_key(row.question) for row in rows}

        if mode == "replace":
            # Keep existing rows but disable them first; incoming rows will be active.
            for faq in existing_faqs:
                faq.is_active = False

        for row in rows:
            key = _normalize_for_key(row.question)
            if not key:
                stats["skipped"] += 1
                continue
            existing = existing_by_key.get(key)
            if existing and mode in {"merge", "replace"}:
                existing.question = row.question
                existing.answer = row.answer
                existing.keywords = row.keywords
                existing.is_active = row.is_active
                stats["updated"] += 1
                continue

            if existing and mode == "append":
                stats["skipped"] += 1
                continue

            db.add(
                FAQ(
                    question=row.question,
                    answer=row.answer,
                    keywords=row.keywords,
                    is_active=row.is_active,
                )
            )
            stats["inserted"] += 1

        if deactivate_missing and mode == "merge":
            for faq in existing_faqs:
                key = _normalize_for_key(faq.question or "")
                if key and key not in incoming_keys and faq.is_active:
                    faq.is_active = False
                    stats["deactivated"] += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed FAQ data safely for production deployments."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=str(DEFAULT_SOURCE),
        help="Path to CSV or JSON FAQ file",
    )
    parser.add_argument(
        "--mode",
        choices=["merge", "append", "replace"],
        default="merge",
        help="merge=upsert by question, append=insert only new, replace=deactivate old then upsert",
    )
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help="Only for merge mode: deactivate existing FAQs not present in source",
    )
    parser.add_argument(
        "--embed-missing",
        action="store_true",
        help="Generate embeddings for source rows that do not include embeddings",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and simulate changes without writing to DB",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any source rows are rejected by validation",
    )
    parser.add_argument(
        "--report-json",
        type=str,
        default="",
        help="Optional path to write a JSON summary report",
    )
    parser.add_argument(
        "--clean-output",
        type=str,
        default="",
        help="Optional path to write validated+deduped FAQ rows (.csv or .json)",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Write cleaned output and exit without DB upsert",
    )
    return parser.parse_args()


def _write_report(path: str, report: dict[str, Any]) -> None:
    if not path:
        return

    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, indent=2)


def seed_faq() -> None:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"FAQ source file not found: {source}")

    rows, rejected = _load_rows(source)
    rows, duplicates = _dedupe_rows(rows)
    cleaned_output_path = ""

    if args.clean_output:
        cleaned_output_path = str(_write_clean_rows(args.clean_output, rows))

    if not rows:
        report = {
            "success": False,
            "error": "No valid FAQ rows found after validation. Check your source file quality.",
            "source": str(source),
            "mode": args.mode,
            "dry_run": args.dry_run,
            "strict": args.strict,
            "clean_only": args.clean_only,
            "cleaned_output": cleaned_output_path,
            "rows_validated": 0,
            "rejected": rejected,
            "input_duplicates_removed": duplicates,
        }
        _write_report(args.report_json, report)
        raise ValueError(report["error"])

    if args.clean_only:
        report = {
            "success": True,
            "source": str(source),
            "mode": args.mode,
            "dry_run": args.dry_run,
            "strict": args.strict,
            "clean_only": args.clean_only,
            "cleaned_output": cleaned_output_path,
            "rows_validated": len(rows),
            "rejected": rejected,
            "input_duplicates_removed": duplicates,
            "stats": {
                "inserted": 0,
                "updated": 0,
                "deactivated": 0,
                "skipped": 0,
            },
        }
        _write_report(args.report_json, report)

        print("FAQ source cleanup completed.")
        print(f"Source: {source}")
        print(f"Rows retained: {len(rows)}")
        print(f"Rejected rows: {sum(rejected.values())}")
        if rejected:
            print(f"Rejected breakdown: {json.dumps(rejected, ensure_ascii=True)}")
        if cleaned_output_path:
            print(f"Cleaned output: {cleaned_output_path}")
        return

    if args.strict and rejected:
        reasons = ", ".join(f"{key}={value}" for key, value in sorted(rejected.items()))
        report = {
            "success": False,
            "error": f"Strict validation failed. Rejected rows: {reasons}",
            "source": str(source),
            "mode": args.mode,
            "dry_run": args.dry_run,
            "strict": args.strict,
            "clean_only": args.clean_only,
            "cleaned_output": cleaned_output_path,
            "rows_validated": len(rows),
            "rejected": rejected,
            "input_duplicates_removed": duplicates,
        }
        _write_report(args.report_json, report)
        raise ValueError(report["error"])

    stats = _upsert_faqs(
        mode=args.mode,
        rows=rows,
        dry_run=args.dry_run,
        deactivate_missing=args.deactivate_missing,
        embed_missing=args.embed_missing,
    )

    report = {
        "success": True,
        "source": str(source),
        "mode": args.mode,
        "dry_run": args.dry_run,
        "strict": args.strict,
        "clean_only": args.clean_only,
        "cleaned_output": cleaned_output_path,
        "rows_validated": len(rows),
        "rejected": rejected,
        "input_duplicates_removed": duplicates,
        "stats": stats,
    }
    _write_report(args.report_json, report)

    print("FAQ seeding completed.")
    print(f"Source: {source}")
    print(f"Mode: {args.mode}")
    print(f"Dry run: {args.dry_run}")
    print(f"Rows validated: {len(rows)}")
    print(f"Rejected rows: {sum(rejected.values())}")
    if rejected:
        print(f"Rejected breakdown: {json.dumps(rejected, ensure_ascii=True)}")
    print(f"Input duplicates removed: {duplicates}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Updated: {stats['updated']}")
    print(f"Deactivated: {stats['deactivated']}")
    print(f"Skipped: {stats['skipped']}")


if __name__ == "__main__":
    seed_faq()