import asyncio
import logging
import os
import sys

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import AsyncMock, MagicMock
import sys as _sys
mock_settings = MagicMock()
mock_settings.DIRECTUS_URL = "http://mock"
mock_settings.DIRECTUS_TOKEN = "mock"
mock_settings.DB_DSN = "postgresql+asyncpg://mock:mock@mock/mock"
_sys.modules['bot.config'] = MagicMock(settings=mock_settings)

# Mock asyncpg and engine creation
_sys.modules['sqlalchemy.ext.asyncio.engine'] = MagicMock()
import sqlalchemy.ext.asyncio
sqlalchemy.ext.asyncio.create_async_engine = MagicMock()

from bot.services.analyzer import Analyzer
from bot.database.models import SizeControl

logging.basicConfig(level=logging.INFO)

async def test_triplex_logic():
    # Мокаем сессию базы данных
    mock_session = AsyncMock()
    
    analyzer = Analyzer(session=mock_session)
    # Наполняем кэш артикулами вручную для тестирования
    analyzer._articles_cache = {
        "4зак": {"glass_article": "4зак", "type_of_processing": "Закаленное"},
        "6Зак": {"glass_article": "6Зак", "type_of_processing": "Закаленное"},
        "4М1": {"glass_article": "4М1", "type_of_processing": "Сырое"},
        "3.3.1TopN": {"glass_article": "3.3.1TopN", "type_of_processing": "Сырое"},
        "4.4.1": {"glass_article": "4.4.1", "type_of_processing": "Сырое"}
    }
    
    # Мокаем кэш пленок для теста
    analyzer._films_cache = {
        "KngEVA0,38": "Для триплекса",
        "KngEVA0,76": "Для триплекса",
        "SolarFilm": "Обычная пленка"
    }

    print("Test 1: parse_formula (Triplex 3.3.1TopN)")
    elements = analyzer.parse_formula("3.3.1TopNxH12x4М1", is_outside=False)
    assert elements[0]["is_triplex"] == True
    assert elements[0]["thickness"] == 6
    assert elements[0]["is_tempered"] == False
    assert elements[1]["type"] == "frame"
    assert elements[2]["article"] == "4М1"
    assert elements[2]["is_tempered"] == False
    print("Test 1 Passed!")

    print("Test 2: parse_formula (Tempered 4зак)")
    elements2 = analyzer.parse_formula("4закxH12x4М1", is_outside=False)
    assert elements2[0]["is_tempered"] == True
    print("Test 2 Passed!")

    print("Test 3: _parse_rule_string for tempered rules")
    rule_parsed = analyzer._parse_rule_string("6Зак/12/4")
    assert rule_parsed[0]["thickness"] == 6
    assert rule_parsed[0]["is_tempered"] == True
    assert rule_parsed[2]["thickness"] == 4
    assert rule_parsed[2]["is_tempered"] == False
    print("Test 3 Passed!")

    # Test check_slip with Mock SizeControl
    mock_rule = MagicMock(spec=SizeControl)
    mock_rule.formula_1_1k = "4/12/4"
    mock_rule.formula_2_1k = "6Зак/12/4"
    
    # Mocking DB response for SizeControl
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_rule
    mock_session.execute.return_value = mock_result
    
    print("Test 4: check_slip (Triplex 4.4.1 passing 4/12/4 rule -> 8 >= 4+2)")
    elements_passing = analyzer.parse_formula("4.4.1xH12x4М1", is_outside=False)
    errors = await analyzer.check_slip(500, 500, elements_passing)
    # 4/12/4 is the first option, should pass because 8 >= 4+2, 12>=12, 4>=4
    assert len(errors) == 0, f"Expected 0 errors, got: {errors}"
    print("Test 4 Passed!")
    
    print("Test 5: check_slip (Triplex 3.3.1 failing against 6Зак/12/4 -> replacing tempered)")
    # Since 4/12/4 passes, we need a rule that strictly tests 6Зак
    mock_rule.formula_1_1k = "6Зак/12/4"
    mock_rule.formula_2_1k = None
    elements_failing = analyzer.parse_formula("4.4.1xH12x4М1", is_outside=False)
    errors = await analyzer.check_slip(500, 500, elements_failing)
    assert len(errors) == 1
    assert "триплексом нельзя заменять закаленное стекло" in errors[0]
    print("Test 5 Passed!")

    print("Test 6: check_slip (Triplex 3.3.1 failing thickness against 6/12/4)")
    mock_rule.formula_1_1k = "6/12/4"
    elements_failing2 = analyzer.parse_formula("3.3.1TopNxH12x4М1", is_outside=False)
    errors = await analyzer.check_slip(500, 500, elements_failing2)
    assert len(errors) == 1
    # expect 6mm < 6mm+2mm
    assert "6 мм (в заказе) < 6 мм + 2 мм (норма)" in errors[0]
    print("Test 6 Passed!")

    print("Test 7: parse_formula (Custom film triplex 4LHSolarxKngEVA0,38x5М1)")
    # Should merge 4LHSolar and 5М1 into a single triplex element with thickness 9
    elements_custom = analyzer.parse_formula("4LHSolarxKngEVA0,38x5М1", is_outside=False)
    assert len(elements_custom) == 1, f"Expected 1 merged element, got {len(elements_custom)}"
    assert elements_custom[0]["thickness"] == 9, "Thickness should be 4 + 5 = 9"
    assert elements_custom[0]["is_triplex"] == True, "Should be flagged as triplex"
    print("Test 7 Passed!")

if __name__ == "__main__":
    asyncio.run(test_triplex_logic())
