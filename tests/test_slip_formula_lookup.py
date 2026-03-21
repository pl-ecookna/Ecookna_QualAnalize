import os
import pathlib
import sys
import logging

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DB_DSN", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
os.environ.setdefault("DIRECTUS_URL", "http://localhost:8055")
os.environ.setdefault("DIRECTUS_TOKEN", "test-token")

from bot.services.analyzer import Analyzer
from bot.services.pdf_parser import PDFParser
from web.app import parse_size_input


class DummyRule:
    marking = "Test Marking"
    formula_1_1k = "4-16-4"
    formula_2_1k = "6-16-4"
    formula_1_2k = "4-10-4-10-4"
    formula_2_2k = None
    formula_1_3k = None
    formula_2_3k = "4-8-4-8-4-8-4"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1520*2730", (1520, 2730)),
        ("1520x2730", (1520, 2730)),
        ("1520х2730", (1520, 2730)),
        (" 1520 × 2730 ", (1520, 2730)),
    ],
)
def test_parse_size_input_accepts_common_delimiters(raw_value, expected):
    assert parse_size_input(raw_value) == expected


def test_parse_size_input_rejects_invalid_format():
    with pytest.raises(HTTPException) as exc_info:
        parse_size_input("1520/2730")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_slip_formulas_by_size_returns_grouped_formulas():
    analyzer = Analyzer(session=None)

    async def fake_find_rule(width, height):
        return DummyRule(), 1500, 2700

    analyzer._find_size_control_rule = fake_find_rule

    result = await analyzer.get_slip_formulas_by_size(1520, 2730)

    assert result["found"] is True
    assert result["width_round"] == 1500
    assert result["height_round"] == 2700
    assert result["marking"] == "Test Marking"
    assert result["formulas"]["1k"] == ["4-16-4", "6-16-4"]
    assert result["formulas"]["2k"] == ["4-10-4-10-4"]
    assert result["formulas"]["3k"] == ["4-8-4-8-4-8-4"]
    assert result["formula_details"]["1k"] == [
        {"formula": "4-16-4", "total_thickness": 8},
        {"formula": "6-16-4", "total_thickness": 10},
    ]
    assert result["formula_details"]["2k"] == [
        {"formula": "4-10-4-10-4", "total_thickness": 12},
    ]
    assert result["formula_details"]["3k"] == [
        {"formula": "4-8-4-8-4-8-4", "total_thickness": 16},
    ]


@pytest.mark.asyncio
async def test_get_slip_formulas_by_size_returns_not_found_payload():
    analyzer = Analyzer(session=None)

    async def fake_find_rule(width, height):
        return None, 1500, 2700

    analyzer._find_size_control_rule = fake_find_rule

    result = await analyzer.get_slip_formulas_by_size(1520, 2730)

    assert result == {
        "found": False,
        "width": 1520,
        "height": 2730,
        "width_round": 1500,
        "height_round": 2700,
        "marking": None,
        "formulas": {},
        "formula_details": {},
    }


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("4-16-4", 8),
        ("6-16-4", 10),
        ("4-10-4-10-4", 12),
        (" 8-14-8 ", 16),
        ("", None),
        (None, None),
        ("abc", None),
    ],
)
def test_get_formula_total_thickness(formula, expected):
    analyzer = Analyzer(session=None)

    assert analyzer.get_formula_total_thickness(formula) == expected


def test_pdf_parser_cleans_service_labels_and_glues_broken_formula():
    text = """Заполнения 88-174-1017 от 06.02.2026
Кол-
Номер Формула Размер Площадь Масса
во
88-174-1017/11/5
4ИxW14RAL7011Arx4М1xW14RAL7011Arx4L
KLV-Standart:Вх.Дверь: 650x1896 1 1.23 39.99
HSolar (40 мм)
Вид СНАРУЖИ на себя
Раскладка отсутствует
Итого по изделию:
Количество элементов - 1
"""

    items = PDFParser.parse_text(text)

    assert len(items) == 1
    assert items[0]["position_num"] == "88-174-1017/11/5"
    assert items[0]["position_formula"] == "4ИxW14RAL7011Arx4М1xW14RAL7011Arx4LHSolar"
    assert items[0]["is_oytside"] is True


def test_analyzer_parse_formula_does_not_split_on_vh_in_service_text():
    analyzer = Analyzer(session=None)

    elements = analyzer.parse_formula(
        "4ИxW14RAL7011Arx4М1xW14RAL7011Arx4LKLV-Standart:Вх.Дверь:",
        is_outside=False,
    )

    assert [element["thickness"] for element in elements] == [4, 14, 4, 14, 4]
    assert len(elements) == 5


def test_analyzer_has_spacer_detects_single_glazing():
    analyzer = Analyzer(session=None)

    assert analyzer.has_spacer("6LHSolarxW14RAL9005x4М1") is True
    assert analyzer.has_spacer("4ИxН14x4М1") is True
    assert analyzer.has_spacer("М1_4мм.") is False
    assert analyzer.has_spacer("") is False


PDF_FIXTURE_PATH = "/Users/romangaleev/Downloads/18-133-1041.pdf"


@pytest.mark.skipif(not os.path.exists(PDF_FIXTURE_PATH), reason="External PDF fixture is not available")
def test_pdf_parser_uses_geometry_columns_for_real_pdf():
    text = PDFParser.extract_text(PDF_FIXTURE_PATH)

    items = PDFParser.parse_text(text)
    by_pos = {item["position_num"]: item for item in items}

    assert by_pos["18-133-1041/3/5"]["position_formula"] == "4ИxН14x4М1xН14x4LHSolar"
    assert by_pos["18-133-1041/3/5"]["is_oytside"] is True
    assert by_pos["18-133-1041/24/5"]["position_formula"] == "4ИxН14x4М1xН14x4LHSolar"
    assert by_pos["18-133-1041/33/5"]["position_formula"] == "4ИxН14x4М1xН14x4LHSolar"
    assert by_pos["18-133-1041/1/5"]["position_formula"] == "4LHSolarxН14x4М1xН14x4И"
    assert by_pos["18-133-1041/20/5"]["position_formula"] == "4MatCrystalVisionxН14x4М1xН14x4LHSolar"
    assert "Kaleva" not in by_pos["18-133-1041/20/5"]["position_formula"]
    assert "СНАРУЖИ" not in by_pos["18-133-1041/20/5"]["position_formula"]
    assert by_pos["18-133-1041/21/11005"]["position_formula"] == "М1_4мм."


@pytest.mark.skipif(not os.path.exists(PDF_FIXTURE_PATH), reason="External PDF fixture is not available")
def test_full_pdf_to_analyzer_chain_normalizes_outside_order():
    text = PDFParser.extract_text(PDF_FIXTURE_PATH)
    items = PDFParser.parse_text(text)
    by_pos = {item["position_num"]: item for item in items}
    analyzer = Analyzer(session=None)

    inside_elements = analyzer.parse_formula(
        by_pos["18-133-1041/1/5"]["position_formula"],
        by_pos["18-133-1041/1/5"]["is_oytside"],
    )
    outside_elements = analyzer.parse_formula(
        by_pos["18-133-1041/3/5"]["position_formula"],
        by_pos["18-133-1041/3/5"]["is_oytside"],
    )
    design_outside_elements = analyzer.parse_formula(
        by_pos["18-133-1041/20/5"]["position_formula"],
        by_pos["18-133-1041/20/5"]["is_oytside"],
    )

    assert [element["article"] for element in inside_elements] == ["4LHSolar", "Н14", "4М1", "Н14", "4И"]
    assert [element["article"] for element in outside_elements] == ["4LHSolar", "Н14", "4М1", "Н14", "4И"]
    assert [element["article"] for element in design_outside_elements] == [
        "4LHSolar",
        "Н14",
        "4М1",
        "Н14",
        "4MatCrystalVision",
    ]


def test_pdf_parser_falls_back_to_regex_with_warning(caplog):
    text = """Заполнения 88-174-1017 от 06.02.2026
Кол-
Номер Формула Размер Площадь Масса
во
88-174-1017/11/5
4ИxW14RAL7011Arx4М1xW14RAL7011Arx4L
KLV-Standart:Вх.Дверь: 650x1896 1 1.23 39.99
HSolar (40 мм)
Вид СНАРУЖИ на себя
Раскладка отсутствует
Итого по изделию:
Количество элементов - 1
"""

    PDFParser._last_extracted_text = text
    PDFParser._last_extracted_pages = [{"text": text, "words": [{"text": "Заполнения", "x0": 10, "x1": 80, "top": 10, "bottom": 20}]}]

    with caplog.at_level(logging.WARNING):
        items = PDFParser.parse_text(text)

    assert len(items) == 1
    assert items[0]["position_formula"] == "4ИxW14RAL7011Arx4М1xW14RAL7011Arx4LHSolar"
    assert "falling back to regex parser" in caplog.text
