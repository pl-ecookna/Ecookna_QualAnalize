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
        {"formula": "4-16-4", "total_thickness": 24},
        {"formula": "6-16-4", "total_thickness": 26},
    ]
    assert result["formula_details"]["2k"] == [
        {"formula": "4-10-4-10-4", "total_thickness": 32},
    ]
    assert result["formula_details"]["3k"] == [
        {"formula": "4-8-4-8-4-8-4", "total_thickness": 40},
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
        ("4-16-4", 24),
        ("6-16-4", 26),
        ("4-10-4-10-4", 32),
        (" 8-14-8 ", 30),
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
    assert analyzer.has_spacer("8Vision71TзакxStructU18плArX:20Ux6М1") is True
    assert analyzer.has_spacer("М1_4мм.") is False
    assert analyzer.has_spacer("") is False
    assert analyzer._calc_cam_count("8Vision71TзакxStructU18плArX:20Ux6М1xStructU12плArX:7x5.5.2StratosafeClear (55мм)") == 2


def test_analyzer_parse_formula_does_not_treat_bronze_as_tempered():
    analyzer = Analyzer(session=None)

    elements = analyzer.parse_formula("6LHSolarBronzexН12x6закxН12x6зак", is_outside=False)
    glasses = [element for element in elements if element["type"] == "glass"]

    assert [element["article"] for element in glasses] == ["6LHSolarBronze", "6зак", "6зак"]
    assert [element["is_tempered"] for element in glasses] == [False, True, True]


def test_analyzer_uses_processing_flag_from_articles_cache_for_tempering():
    analyzer = Analyzer(session=None)
    analyzer._articles_cache = {
        "6LHSolarBronze": {"type_of_processing": "Закаленное"},
    }

    elements = analyzer.parse_formula("6LHSolarBronzexН12x4М1", is_outside=False)
    glasses = [element for element in elements if element["type"] == "glass"]

    assert [element["is_tempered"] for element in glasses] == [True, False]


def test_analyzer_treats_xu_as_frame_marker():
    analyzer = Analyzer(session=None)

    elements = analyzer.parse_formula(
        "8Vision71TзакxStructU18плArX:20Ux6М1xStructU12плArX:7x5.5.2StratosafeClear (55мм)",
        is_outside=False,
    )

    assert [element["type"] for element in elements] == ["glass", "frame", "glass", "frame", "glass"]
    assert analyzer.has_spacer("8Vision71TзакxStructU18плArX:20Ux6М1") is True


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


def test_pdf_parser_geometry_keeps_formula_prefix_row_above_position_number():
    text = """Заполнения 88-177-1030 от 17.03.2026
Кол-
Номер Формула Размер Площадь Масса
во
8LPHPNeutral60/40закxW18RAL7040Arx6М1
88-177-1030/1/5
xW18RAL7040Arx6М1xW18RAL7040Arx6LP 1772x2448 3 13.01 874.75
Заполнение
PremiumTзак (80 мм)
Раскладка отсутствует
Итого по изделию:
Количество элементов - 3
"""

    PDFParser._last_extracted_text = text
    PDFParser._last_extracted_pages = [
        {
            "text": text,
            "words": [
                {"text": "Кол-", "x0": 457.5, "x1": 480.0, "top": 56.6, "bottom": 62.0},
                {"text": "Номер", "x0": 58.1, "x1": 95.0, "top": 62.6, "bottom": 68.0},
                {"text": "Формула", "x0": 245.9, "x1": 300.0, "top": 62.6, "bottom": 68.0},
                {"text": "Размер", "x0": 401.7, "x1": 450.0, "top": 62.6, "bottom": 68.0},
                {"text": "Площадь", "x0": 491.8, "x1": 540.0, "top": 62.6, "bottom": 68.0},
                {"text": "Масса", "x0": 552.2, "x1": 590.0, "top": 62.6, "bottom": 68.0},
                {"text": "во", "x0": 462.7, "x1": 475.0, "top": 68.6, "bottom": 74.0},
                {"text": "8LPHPNeutral60/40закxW18RAL7040Arx6М1", "x0": 154.1, "x1": 387.4, "top": 84.3, "bottom": 90.0},
                {"text": "88-177-1030/1/5", "x0": 35.5, "x1": 116.2, "top": 90.3, "bottom": 96.0},
                {"text": "xW18RAL7040Arx6М1xW18RAL7040Arx6LP", "x0": 155.9, "x1": 385.7, "top": 96.3, "bottom": 102.0},
                {"text": "1772x2448", "x0": 394.0, "x1": 450.0, "top": 96.3, "bottom": 102.0},
                {"text": "3", "x0": 466.3, "x1": 470.0, "top": 96.3, "bottom": 102.0},
                {"text": "13.01", "x0": 503.5, "x1": 535.0, "top": 96.3, "bottom": 102.0},
                {"text": "874.75", "x0": 552.3, "x1": 585.0, "top": 96.3, "bottom": 102.0},
                {"text": "Заполнение", "x0": 43.2, "x1": 110.0, "top": 102.3, "bottom": 108.0},
                {"text": "PremiumTзак", "x0": 214.4, "x1": 285.2, "top": 108.3, "bottom": 114.0},
                {"text": "(80", "x0": 288.2, "x1": 305.0, "top": 108.3, "bottom": 114.0},
                {"text": "мм)", "x0": 307.1, "x1": 323.0, "top": 108.3, "bottom": 114.0},
                {"text": "Раскладка", "x0": 459.1, "x1": 518.9, "top": 124.1, "bottom": 130.0},
                {"text": "отсутствует", "x0": 518.9, "x1": 590.0, "top": 124.1, "bottom": 130.0},
                {"text": "Итого", "x0": 0.8, "x1": 33.0, "top": 139.1, "bottom": 145.0},
                {"text": "по", "x0": 34.9, "x1": 49.0, "top": 139.1, "bottom": 145.0},
                {"text": "изделию:", "x0": 51.3, "x1": 95.0, "top": 139.1, "bottom": 145.0},
            ],
        }
    ]

    items = PDFParser.parse_text(text)

    assert len(items) == 1
    assert items[0]["position_num"] == "88-177-1030/1/5"
    assert items[0]["position_formula"] == "8LPHPNeutral60/40закxW18RAL7040Arx6М1xW18RAL7040Arx6М1xW18RAL7040Arx6LPPremiumTзак"
