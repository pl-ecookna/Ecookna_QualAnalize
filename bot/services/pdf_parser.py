import logging
import re
from typing import Any, Dict, List, Optional

import pdfplumber

logger = logging.getLogger(__name__)


class PDFParser:
    NUMBER_RE = re.compile(r"(\d{2}-\d{3}-\s*\d{4}\/\d+\/\d+(?:[\/\w-]*))")
    ANCHOR_RE = re.compile(r"(\d+)\s*[x×хХ]\s*(\d+)\s+(\d+)\s+([\d.,]+)(?:\s+([\d.,]+))?")
    THICK_RE = re.compile(r"\((\d+)(?:\s*мм)?\)")
    FORMULA_TOKEN_RE = re.compile(r"^[0-9A-Za-zА-Яа-я_.,+\-/]+$")
    SIZE_TOKEN_RE = re.compile(r"^\d+\s*[x×хХ]\s*\d+$")
    HEADER_TOKENS = {"Номер", "Формула", "Размер", "Площадь", "Масса"}
    STOP_MARKERS = {
        "ВИД",
        "РАСКЛАДКА",
        "ВКЛЕЙКА",
        "КОЛИЧЕСТВО",
        "ПЛОЩАДЬ",
        "МАССА",
        "ИТОГО",
        "ЭСКИЗ",
        "ВИД",
        "ЧЕРТЕЖ",
        "ЭЛЕМЕНТ",
        "МАРКИРОВКА",
    }

    LAYOUT_RE = re.compile(r"Раскладка\s+([^\r\n]+)", re.IGNORECASE)
    SPLIT_RE = re.compile(r"Итого по изделию:", re.IGNORECASE)

    _last_extracted_text: Optional[str] = None
    _last_extracted_pages: Optional[List[Dict[str, Any]]] = None

    @staticmethod
    def extract_text(file_path: str) -> str:
        """Extracts full text from a PDF file using pdfplumber."""
        full_text: List[str] = []
        page_payloads: List[Dict[str, Any]] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
                    tables_payload: List[Dict[str, Any]] = []
                    for table in page.find_tables():
                        table_rows = table.extract() or []
                        tables_payload.append(
                            {
                                "bbox": table.bbox,
                                "rows": table_rows,
                            }
                        )
                    page_payloads.append(
                        {
                            "text": text,
                            "words": words,
                            "tables": tables_payload,
                        }
                    )
                    if text:
                        full_text.append(text)

            result = "\n".join(full_text)
            PDFParser._last_extracted_text = result
            PDFParser._last_extracted_pages = page_payloads
            return result
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            raise

    @staticmethod
    def _normalize_spaces(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _is_service_token(cls, token: str) -> bool:
        token_upper = token.upper()
        if ":" in token:
            return True
        if token_upper in cls.STOP_MARKERS:
            return True
        return token.startswith("(")

    @classmethod
    def _looks_like_formula_start(cls, token: str) -> bool:
        token_lc = token.lower()
        has_x = "x" in token_lc or "х" in token_lc

        # Если это чистое число > 80, скорее всего это масса или площадь, а не начало формулы
        if not has_x and re.match(r"^\d+(?:[.,]\d+)?$", token):
            try:
                val = float(token.replace(",", "."))
                if val > 80:
                    return False
            except ValueError:
                pass

        return (
            has_x and ":" not in token
            or re.match(r"^[0-9]", token) is not None
            or re.match(r"^[HWНШU]", token, re.IGNORECASE) is not None
        )

    @classmethod
    def _extract_formula_source(cls, raw_formula: str) -> str:
        tokens = cls._normalize_spaces(raw_formula).split()
        if not tokens:
            return ""

        start_idx = None
        for idx, token in enumerate(tokens):
            if cls._looks_like_formula_start(token):
                start_idx = idx
                break

        if start_idx is None:
            return ""

        formula_tokens = []
        for token in tokens[start_idx:]:
            if cls._is_service_token(token):
                break
            formula_tokens.append(token)

        return "".join(formula_tokens)

    @classmethod
    def _extract_formula_continuation(cls, post_context: str) -> str:
        continuation = []
        for token in cls._normalize_spaces(post_context).split():
            if cls._is_service_token(token):
                break
            if not cls.FORMULA_TOKEN_RE.match(token):
                break
            continuation.append(token)

        return "".join(continuation)

    @staticmethod
    def _word_text(word: Dict[str, Any]) -> str:
        return str(word.get("text", "")).strip()

    @staticmethod
    def _row_top(word: Dict[str, Any]) -> float:
        return round(float(word.get("top", 0.0)), 1)

    @classmethod
    def _group_words_into_rows(cls, words: List[Dict[str, Any]], tolerance: float = 3.0) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
            text = cls._word_text(word)
            if not text:
                continue

            if rows and abs(float(word["top"]) - rows[-1]["top"]) <= tolerance:
                rows[-1]["words"].append(word)
                current = rows[-1]
                current["top"] = min(current["top"], float(word["top"]))
                current["bottom"] = max(current["bottom"], float(word["bottom"]))
            else:
                rows.append(
                    {
                        "top": float(word["top"]),
                        "bottom": float(word["bottom"]),
                        "words": [word],
                    }
                )

        for row in rows:
            row["words"].sort(key=lambda item: float(item["x0"]))
            row["text"] = " ".join(cls._word_text(word) for word in row["words"])

        return rows

    @classmethod
    def _find_table_headers(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        headers: List[Dict[str, float]] = []
        for row in rows:
            positions: Dict[str, float] = {}
            for word in row["words"]:
                text = cls._word_text(word)
                if text in cls.HEADER_TOKENS:
                    positions[text] = float(word["x0"])

            if {"Номер", "Формула", "Размер", "Площадь", "Масса"}.issubset(positions):
                headers.append(
                    {
                        "top": row["top"],
                        "bottom": row["bottom"],
                        "number_left": positions["Номер"],
                        "formula_left": (positions["Номер"] + positions["Формула"]) / 2,
                        "size_left": positions["Размер"],
                    }
                )

        return headers

    @classmethod
    def _normalize_formula(cls, raw_formula: str) -> str:
        # Use token-based truncation to avoid picking up text after formula ends
        clean = cls._extract_formula_source(raw_formula)
        return clean.replace(" ", "")

    @classmethod
    def _parse_numbers_from_anchor(cls, anchor_row_text: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"(\d+)\s*[x×хХ]\s*(\d+)", anchor_row_text)
        if not match:
            return None

        try:
            return {
                "position_width": int(match.group(1)),
                "position_hight": int(match.group(2)),
            }
        except (ValueError, IndexError):
            return None

    @classmethod
    def _rows_to_text(cls, rows: List[Dict[str, Any]]) -> str:
        return "\n".join(row["text"] for row in rows)

    @classmethod
    def _extract_layout(cls, rows: List[Dict[str, Any]]) -> str:
        text = cls._rows_to_text(rows)
        match = cls.LAYOUT_RE.search(text)
        return match.group(1).strip() if match else "отсутствует"

    @classmethod
    def _extract_is_outside(cls, rows: List[Dict[str, Any]], raw_formula: str) -> bool:
        full_text_check = f"{cls._rows_to_text(rows)} {raw_formula}".upper()
        return (
            "СНАРУЖИ" in full_text_check
            or "НАРУЖУ" in full_text_check
        )

    @classmethod
    def _parse_item_from_rows(
        cls,
        rows: List[Dict[str, Any]],
        formula_left: float,
        size_left: float,
    ) -> Optional[Dict[str, Any]]:
        number_row = None
        anchor_row = None
        for row in rows:
            if number_row is None:
                for word in row["words"]:
                    text = cls._word_text(word)
                    if cls.NUMBER_RE.fullmatch(text):
                        number_row = row
                        break

            if anchor_row is None:
                anchor_words = [
                    word for word in row["words"] if float(word["x0"]) >= formula_left and float(word["x1"]) <= size_left + 220
                ]
                anchor_text = " ".join(cls._word_text(word) for word in anchor_words)
                if cls.ANCHOR_RE.search(anchor_text):
                    anchor_row = row

            if number_row is not None and anchor_row is not None:
                break

        if number_row is None or anchor_row is None:
            return None

        position_num = next(
            cls._word_text(word)
            for word in number_row["words"]
            if cls.NUMBER_RE.fullmatch(cls._word_text(word))
        )

        formula_words: List[Dict[str, Any]] = []
        for row in rows:
            for word in row["words"]:
                if float(word["x0"]) >= formula_left and float(word["x1"]) < size_left:
                    formula_words.append(word)

        formula_words.sort(key=lambda item: (float(item["top"]), float(item["x0"])))
        raw_formula = " ".join(cls._word_text(word) for word in formula_words if cls._word_text(word))
        if not raw_formula:
            return None

        numbers = cls._parse_numbers_from_anchor(anchor_row["text"])
        if numbers is None:
            return None

        item = {
            "position_num": position_num.replace("\n", "").strip(),
            "position_formula": cls._normalize_formula(raw_formula),
            "is_oytside": cls._extract_is_outside(rows, raw_formula),
            "position_width": numbers["position_width"],
            "position_hight": numbers["position_hight"],
        }
        return item

    @classmethod
    def _row_formula_words(
        cls,
        row: Dict[str, Any],
        formula_left: float,
        size_left: float,
    ) -> List[Dict[str, Any]]:
        return [
            word
            for word in row["words"]
            if float(word["x0"]) >= formula_left and float(word["x1"]) < size_left
        ]

    @classmethod
    def _is_formula_prefix_row(
        cls,
        row: Dict[str, Any],
        formula_left: float,
        size_left: float,
    ) -> bool:
        if any(cls.NUMBER_RE.fullmatch(cls._word_text(word)) for word in row["words"]):
            return False

        formula_words = cls._row_formula_words(row, formula_left, size_left)
        if not formula_words:
            return False

        formula_text = cls._normalize_spaces(" ".join(cls._word_text(word) for word in formula_words))
        if not formula_text:
            return False

        if cls._is_service_token(formula_text):
            return False

        if cls.ANCHOR_RE.search(formula_text):
            return False

        if re.fullmatch(r"[\d\s.,-]+", formula_text):
            return False

        return cls._looks_like_formula_start(formula_text)

    @classmethod
    def _take_formula_prefix_rows(
        cls,
        rows_before_number: List[Dict[str, Any]],
        formula_left: float,
        size_left: float,
    ) -> List[Dict[str, Any]]:
        prefix_rows: List[Dict[str, Any]] = []

        for row in reversed(rows_before_number):
            if cls._is_formula_prefix_row(row, formula_left, size_left):
                prefix_rows.append(row)
                continue
            break

        prefix_rows.reverse()
        return prefix_rows

    @classmethod
    def _parse_page_by_geometry(cls, page_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = cls._group_words_into_rows(page_words)
        headers = cls._find_table_headers(rows)
        if not headers:
            return []

        items: List[Dict[str, Any]] = []
        header_index = 0
        current_header = headers[header_index]
        current_rows: List[Dict[str, Any]] = []
        pre_number_rows: List[Dict[str, Any]] = []

        def flush_current_rows() -> None:
            nonlocal current_rows, pre_number_rows
            if not current_rows:
                pre_number_rows = []
                return
            item = cls._parse_item_from_rows(
                current_rows,
                formula_left=current_header["formula_left"],
                size_left=current_header["size_left"],
            )
            if item:
                logger.info(
                    "Geometry parser item %s: Raw='%s', Parsed='%s', IsOutside=%s",
                    item["position_num"],
                    item["raw_formula"],
                    item["position_formula"],
                    item["is_oytside"],
                )
                items.append(item)
            current_rows = []
            pre_number_rows = []

        for row in rows:
            if header_index + 1 < len(headers) and row["top"] >= headers[header_index + 1]["top"]:
                flush_current_rows()
                header_index += 1
                current_header = headers[header_index]
                pre_number_rows = []

            if row["top"] <= current_header["bottom"]:
                continue

            if row["text"].startswith("Итого по изделию:"):
                flush_current_rows()
                continue

            has_number = any(
                cls.NUMBER_RE.fullmatch(cls._word_text(word))
                and float(word["x1"]) <= current_header["formula_left"]
                for word in row["words"]
            )
            if has_number:
                if current_rows:
                    flush_current_rows()
                current_rows = cls._take_formula_prefix_rows(
                    pre_number_rows,
                    formula_left=current_header["formula_left"],
                    size_left=current_header["size_left"],
                ) + [row]
                pre_number_rows = []
                continue

            if current_rows:
                current_rows.append(row)
            else:
                pre_number_rows.append(row)

        flush_current_rows()
        return items

    @classmethod
    def _parse_text_by_geometry(cls, text: str) -> Optional[List[Dict[str, Any]]]:
        if text != cls._last_extracted_text or not cls._last_extracted_pages:
            return None

        items: List[Dict[str, Any]] = []
        geometry_used = False
        for page_payload in cls._last_extracted_pages:
            page_items = cls._parse_page_by_geometry(page_payload.get("words", []))
            if page_items:
                geometry_used = True
                items.extend(page_items)

        if not geometry_used:
            return None

        return items

    @classmethod
    def _parse_text_by_tables(cls, text: str) -> Optional[List[Dict[str, Any]]]:
        if text != cls._last_extracted_text or not cls._last_extracted_pages:
            return None

        items: List[Dict[str, Any]] = []
        table_used = False

        for page_payload in cls._last_extracted_pages:
            for table_payload in page_payload.get("tables", []):
                rows = table_payload.get("rows") or []
                if not rows:
                    continue

                header = rows[0]
                try:
                    number_idx = header.index("Номер")
                    formula_idx = header.index("Формула")
                    size_idx = header.index("Размер")
                except ValueError:
                    continue

                table_used = True

                for row in rows[1:]:
                    if not row or number_idx >= len(row) or formula_idx >= len(row):
                        continue

                    number_cell = row[number_idx] or ""
                    formula_cell = row[formula_idx] or ""
                    size_cell = row[size_idx] if size_idx < len(row) else None

                    if not number_cell.strip() or not formula_cell.strip():
                        continue

                    number_match = cls.NUMBER_RE.search(number_cell.replace("\n", " "))
                    if not number_match:
                        continue

                    size_match = re.search(r"(\d+)\s*x\s*(\d+)", size_cell or "", re.IGNORECASE)
                    if not size_match:
                        size_match = re.search(r"(\d+)\s*[x×хХ]\s*(\d+)", size_cell or "", re.IGNORECASE)
                    if not size_match:
                        continue

                    try:
                        position_width = int(size_match.group(1))
                        position_hight = int(size_match.group(2))
                    except ValueError:
                        continue

                    position_num = number_match.group(1).replace("\n", "").strip()
                    raw_formula = cls._normalize_spaces(formula_cell)

                    position_formula = re.sub(r"\s+", "", raw_formula)

                    item = {
                        "position_num": position_num,
                        "position_formula": position_formula,
                        "position_width": position_width,
                        "position_hight": position_hight,
                        "is_oytside": cls._extract_is_outside([{"text": raw_formula, "words": []}], raw_formula),
                    }
                    items.append(item)

        if not table_used:
            return None

        return items

    @classmethod
    def _parse_text_by_regex(cls, text: str) -> List[Dict]:
        items = []
        blocks = cls.SPLIT_RE.split(text)

        for block in blocks:
            anchors = list(cls.ANCHOR_RE.finditer(block))
            last_end = 0

            for i, anchor in enumerate(anchors):
                pre_context = block[last_end:anchor.start()]
                num_matches = list(cls.NUMBER_RE.finditer(pre_context))
                if not num_matches:
                    logger.warning(f"No number found for anchor at {anchor.start()}")
                    continue

                num_match = num_matches[-1]
                raw_num = num_match.group(1)
                raw_formula_chunk = pre_context[num_match.end():].strip()
                suffix_has_formula = "x" in raw_formula_chunk.lower() or "х" in raw_formula_chunk.lower()
                prefix_text = pre_context[:num_match.start()].strip()

                if not suffix_has_formula and ("x" in prefix_text.lower() or "х" in prefix_text.lower()):
                    raw_formula_source = prefix_text
                else:
                    raw_formula_source = raw_formula_chunk

                post_context_end = anchors[i + 1].start() if i + 1 < len(anchors) else len(block)
                post_context = block[anchor.end():post_context_end]

                suffix_text = raw_formula_chunk.strip()
                is_suffix_formula = "x" in suffix_text.lower() or "х" in suffix_text.lower()
                position_num = raw_num.replace("\n", "").strip()
                if suffix_text and not is_suffix_formula:
                    position_num = f"{position_num} {suffix_text}"
                position_num = re.sub(r"\s+", " ", position_num).strip()

                raw_formula_clean = cls._normalize_spaces(raw_formula_source)
                full_text_check = (prefix_text + " " + raw_formula_chunk + " " + post_context).upper()
                is_outside = (
                    "СНАРУЖИ" in full_text_check
                    or "НАРУЖУ" in full_text_check
                )

                position_formula = cls._extract_formula_source(raw_formula_clean)
                formula_continuation = cls._extract_formula_continuation(post_context)
                if formula_continuation:
                    position_formula += formula_continuation

                position_formula = position_formula.replace(" ", "")
                logger.info(
                    "Regex parser item %s: Raw='%s', Parsed='%s', IsOutside=%s",
                    position_num,
                    raw_formula_clean,
                    position_formula,
                    is_outside,
                )

                try:
                    width = int(anchor.group(1))
                    height = int(anchor.group(2))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing numbers for item {position_num}: {e}")
                    continue

                items.append(
                    {
                        "position_num": position_num,
                        "position_formula": position_formula,
                        "position_width": width,
                        "position_hight": height,
                        "is_oytside": is_outside,
                    }
                )

                last_end = anchor.end()

        return items

    @classmethod
    def parse_text(cls, text: str) -> List[Dict]:
        """Parses the extracted text into structural items."""
        table_items = cls._parse_text_by_tables(text)
        if table_items is not None:
            return table_items

        geometry_items = cls._parse_text_by_geometry(text)
        if geometry_items is not None:
            return geometry_items

        if text == cls._last_extracted_text and cls._last_extracted_pages:
            logger.warning("Geometry parser unavailable for this PDF page layout, falling back to regex parser.")

        return cls._parse_text_by_regex(text)
