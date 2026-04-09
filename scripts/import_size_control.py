import argparse
import asyncio
import csv
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.services.directus import DirectusClient


DEFAULT_COLLECTION = "size_control"
NUMERIC_HEADER_RE = re.compile(r"^\d+(?:\.\d+)?$")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SizeControlRow:
    dim1: int
    dim2: int
    marking: str

    def payload(self) -> dict:
        return {
            "dim1": self.dim1,
            "dim2": self.dim2,
            "marking": self.marking,
        }


def normalize_text(value: str) -> str:
    return SPACE_RE.sub(" ", value or "").strip()


def parse_dimension(value: str) -> Optional[int]:
    text = normalize_text(value)
    if not text:
        return None
    if not NUMERIC_HEADER_RE.match(text):
        return None
    return int(float(text))


def build_row(dim1: int, dim2: int, value: str) -> SizeControlRow:
    return SizeControlRow(
        dim1=dim1,
        dim2=dim2,
        marking=normalize_text(value),
    )


def iter_rows_from_csv(path: Path) -> Iterable[SizeControlRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        header = next(reader, None)
        if not header:
            return

        numeric_columns: list[tuple[int, int]] = []
        for idx in range(1, len(header)):
            dim = parse_dimension(header[idx])
            if dim is not None:
                numeric_columns.append((idx, dim))

        for row in reader:
            if not row:
                continue

            row_dim = parse_dimension(row[0])
            if row_dim is None:
                continue

            for col_idx, col_dim in numeric_columns:
                if col_idx >= len(row):
                    continue
                value = normalize_text(row[col_idx])
                if not value:
                    continue

                dim1, dim2 = sorted((row_dim, col_dim))
                yield build_row(dim1, dim2, value)


def load_csv_source(input_path: Optional[str], url: Optional[str]) -> Path:
    if input_path and url:
        raise SystemExit("Укажите только один источник: --input или --url")

    if not input_path and not url:
        raise SystemExit("Нужно указать источник CSV: --input или --url")

    if input_path:
        path = Path(input_path).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Файл не найден: {path}")
        return path

    parsed = urllib.parse.urlparse(url or "")
    file_id_match = re.search(r"/d/([a-zA-Z0-9_-]+)", parsed.path)
    file_id = file_id_match.group(1) if file_id_match else None
    if not file_id:
        query_id = urllib.parse.parse_qs(parsed.query).get("id", [None])[0]
        file_id = query_id
    if not file_id:
        raise SystemExit("Не удалось извлечь file id из URL Google Drive")

    download_url = f"https://drive.usercontent.google.com/uc?id={file_id}&export=download"
    target_path = Path("/tmp") / f"size_control_{file_id}.csv"
    ssl_context = ssl._create_unverified_context()
    with urllib.request.urlopen(download_url, context=ssl_context) as response, target_path.open("wb") as out:
        out.write(response.read())
    return target_path


async def upsert_rows(
    client: DirectusClient,
    collection: str,
    rows: list[SizeControlRow],
    dry_run: bool,
) -> tuple[int, int]:
    created = 0
    updated = 0
    existing_items = await client.find_items(collection, params={"limit": -1, "fields": "id,dim1,dim2"})
    existing_by_pair = {
        tuple(sorted((int(item["dim1"]), int(item["dim2"])))): item
        for item in existing_items.get("data", [])
        if item.get("dim1") is not None and item.get("dim2") is not None
    }

    for index, row in enumerate(rows, start=1):
        if index % 100 == 0:
            print(f"Обработано строк: {index}/{len(rows)}")

        existing_item = existing_by_pair.get(tuple(sorted((row.dim1, row.dim2))))

        if dry_run:
            action = "UPDATE" if existing_item else "CREATE"
            print(f"{action} {row.dim1}x{row.dim2}: {row.marking}")
            continue

        payload = row.payload()
        if existing_item:
            await client.update_item(collection, existing_item["id"], payload)
            updated += 1
        else:
            await client.create_item(collection, payload)
            created += 1

    return created, updated


async def delete_missing(
    client: DirectusClient,
    collection: str,
    keep_pairs: set[tuple[int, int]],
    dry_run: bool,
) -> int:
    all_items = await client.find_items(collection, params={"limit": -1, "fields": "id,dim1,dim2"})
    deleted = 0
    for item in all_items.get("data", []):
        pair = tuple(sorted((int(item["dim1"]), int(item["dim2"]))))
        if pair in keep_pairs:
            continue
        if dry_run:
            print(f"DELETE {pair[0]}x{pair[1]}")
            continue
        await client.delete_item(collection, item["id"])
        deleted += 1
    return deleted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Загрузка таблицы слипаемости в Directus size_control")
    parser.add_argument("--input", help="Путь к CSV файлу")
    parser.add_argument("--url", help="Ссылка Google Drive на CSV")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Имя коллекции Directus")
    parser.add_argument("--dry-run", action="store_true", help="Показать изменения без записи в Directus")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Удалить записи, которых больше нет в CSV, чтобы коллекция совпадала с источником",
    )
    return parser


async def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    directus_url = os.getenv("DIRECTUS_URL")
    directus_token = os.getenv("DIRECTUS_TOKEN")
    if not directus_url or not directus_token:
        raise SystemExit("Нужны переменные окружения DIRECTUS_URL и DIRECTUS_TOKEN")

    source_path = load_csv_source(args.input, args.url)
    rows = list(iter_rows_from_csv(source_path))
    if not rows:
        raise SystemExit("В CSV не найдено данных для загрузки")

    client = DirectusClient(base_url=directus_url, token=directus_token, verify_ssl=False)
    created, updated = await upsert_rows(client, args.collection, rows, args.dry_run)

    deleted = 0
    if args.sync:
        keep_pairs = {tuple(sorted((row.dim1, row.dim2))) for row in rows}
        deleted = await delete_missing(client, args.collection, keep_pairs, args.dry_run)

    total = len(rows)
    if args.dry_run:
        print(f"DRY RUN: {total} строк подготовлено, create/update/delete не выполнялись")
    else:
        print(f"Готово: создано {created}, обновлено {updated}, удалено {deleted}, всего строк из CSV {total}")


if __name__ == "__main__":
    asyncio.run(main())
