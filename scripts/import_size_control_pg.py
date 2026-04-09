import argparse
import asyncio
import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True)
class SizeControlRow:
    dim1: int
    dim2: int
    marking: str


def normalize(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_dimension(value: str) -> Optional[int]:
    text = normalize(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def canonical_pair(dim1: int, dim2: int) -> tuple[int, int]:
    return tuple(sorted((dim1, dim2)))


def load_rows(path: Path) -> list[SizeControlRow]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader, None)
    if not header:
        return []

    numeric_columns: list[tuple[int, int]] = []
    for idx in range(1, len(header)):
        dim = parse_dimension(header[idx])
        if dim is not None:
            numeric_columns.append((idx, dim))

    rows: list[SizeControlRow] = []
    for raw in reader:
        if not raw:
            continue

        row_dim = parse_dimension(raw[0])
        if row_dim is None:
            continue

        for idx, col_dim in numeric_columns:
            if idx >= len(raw):
                continue
            marking = normalize(raw[idx])
            if not marking:
                continue
            dim1, dim2 = canonical_pair(row_dim, col_dim)
            rows.append(SizeControlRow(dim1=dim1, dim2=dim2, marking=marking))

    return rows


async def upsert_rows(session: AsyncSession, table: Table, rows: list[SizeControlRow]) -> tuple[int, int]:
    result = await session.execute(select(table.c.id, table.c.dim1, table.c.dim2))
    existing = {
        canonical_pair(int(row.dim1), int(row.dim2)): int(row.id)
        for row in result.all()
        if row.dim1 is not None and row.dim2 is not None
    }

    created = 0
    updated = 0

    for index, row in enumerate(rows, start=1):
        if index % 100 == 0:
            print(f"Обработано строк: {index}/{len(rows)}")

        item_id = existing.get(canonical_pair(row.dim1, row.dim2))
        if item_id is None:
            await session.execute(
                insert(table).values(dim1=row.dim1, dim2=row.dim2, marking=row.marking)
            )
            created += 1
        else:
            await session.execute(
                update(table)
                .where(table.c.id == item_id)
                .values(dim1=row.dim1, dim2=row.dim2, marking=row.marking)
            )
            updated += 1

    await session.commit()
    return created, updated


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Импорт size_control напрямую в PostgreSQL")
    parser.add_argument("--input", required=True, help="Путь к CSV файлу")
    parser.add_argument("--dsn", default=os.getenv("DB_DSN"), help="PostgreSQL DSN")
    parser.add_argument("--dry-run", action="store_true", help="Показать план импорта без записи")
    args = parser.parse_args()

    if not args.dsn:
        raise SystemExit("Нужен DB_DSN")

    path = Path(args.input).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Файл не найден: {path}")

    rows = load_rows(path)
    if not rows:
        raise SystemExit("В CSV не найдено данных для загрузки")

    metadata = MetaData(schema="public")
    size_control = Table(
        "size_control",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("dim1", BigInteger),
        Column("dim2", BigInteger),
        Column("marking", String),
    )

    engine = create_async_engine(args.dsn, pool_pre_ping=True, echo=False, connect_args={"ssl": False})
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        if args.dry_run:
            result = await session.execute(select(size_control.c.id, size_control.c.dim1, size_control.c.dim2))
            existing = {
                canonical_pair(int(row.dim1), int(row.dim2))
                for row in result.all()
                if row.dim1 is not None and row.dim2 is not None
            }
            created = sum(1 for row in rows if canonical_pair(row.dim1, row.dim2) not in existing)
            updated = len(rows) - created
            print(f"DRY RUN: всего строк {len(rows)}, create {created}, update {updated}")
        else:
            created, updated = await upsert_rows(session, size_control, rows)
            print(f"Готово: создано {created}, обновлено {updated}, всего строк {len(rows)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
