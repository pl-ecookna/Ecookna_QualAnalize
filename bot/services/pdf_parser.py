import re
import pdfplumber
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class PDFParser:
    # Regex Patterns
    # Номер: допускаем пробелы/переносы внутри
    # 1: Number, 2: Raw Formula, 3: Thickness, 4: Width, 5: Height, 6: Count, 7: Area, 8: Mass
    # Regex Patterns
    # 1: Number
    NUMBER_RE = re.compile(r"(\d{2}-\d{3}-\s*\d{4}\/\d+\/\d+(?:[\/\w-]*))")
    
    # Anchor: Width x Height Count Area Mass
    # 1: Width, 2: Height, 3: Count, 4: Area, 5: Mass
    ANCHOR_RE = re.compile(
        r"(\d+)\s*[x×хХ]\s*(\d+)\s+(\d+)\s+([\d.,]+)\s+([\d.,]+)"
    )
    
    # Thickness RE (for context search)
    THICK_RE = re.compile(r"\((\d+)(?:\s*мм)?\)")
    
    LAYOUT_RE = re.compile(r"Раскладка\s+([^\r\n]+)", re.IGNORECASE)
    SPLIT_RE = re.compile(r"Итого по изделию:", re.IGNORECASE)

    @staticmethod
    def extract_text(file_path: str) -> str:
        """Extracts full text from a PDF file using pdfplumber."""
        full_text = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
            return "\n".join(full_text)
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            raise

    @staticmethod
    def parse_text(text: str) -> List[Dict]:
        """Parses the extracted text into structural items."""
        items = []
        blocks = PDFParser.SPLIT_RE.split(text)

        for block in blocks:
            # Extract Layout (Raskladka) if present in the block
            layout_match = PDFParser.LAYOUT_RE.search(block)
            layout = layout_match.group(1).strip() if layout_match else "отсутствует"

            # Iterate over all items in the block using Anchors
            # Anchor: Width x Height Count ...
            anchors = list(PDFParser.ANCHOR_RE.finditer(block))
            last_end = 0
            
            for i, anchor in enumerate(anchors):
                # 1. Define Search Window for Number
                # From end of previous item (or 0) to start of this anchor
                pre_context = block[last_end:anchor.start()]
                
                # Find Number (take the last one found in this window)
                num_matches = list(PDFParser.NUMBER_RE.finditer(pre_context))
                if not num_matches:
                    logger.warning(f"No number found for anchor at {anchor.start()}")
                    continue
                
                num_match = num_matches[-1]
                raw_num = num_match.group(1)
                
                # 2. Extract Formula
                # Text between Number End and Anchor Start
                raw_formula_chunk = pre_context[num_match.end():].strip()
                
                # 3. Extract Post-Context
                # From Anchor End to start of next anchor (or block end)
                if i + 1 < len(anchors):
                    post_context_end = anchors[i+1].start()
                else:
                    post_context_end = len(block)
                
                post_context = block[anchor.end():post_context_end]
                
                # 4. Extract Data from Anchor
                raw_width = anchor.group(1)
                raw_height = anchor.group(2)
                raw_count = anchor.group(3)
                raw_area = anchor.group(4)
                raw_mass = anchor.group(5)

                # 5. Clean and Normalize
                position_num = raw_num.replace(" ", "").replace("\n", "").strip()
                raw_formula_clean = re.sub(r"\s+", " ", raw_formula_chunk).strip()
                
                # Extract Thickness
                # Check formula chunk first, then post-context
                thick_match = PDFParser.THICK_RE.search(raw_formula_clean)
                if not thick_match:
                    thick_match = PDFParser.THICK_RE.search(post_context)
                # thickness = int(thick_match.group(1)) if thick_match else 0 # Not strictly used yet
                
                # Check is_outside
                full_text_check = (raw_formula_clean + " " + post_context).upper()
                
                is_outside = (
                    "СНАРУЖИ" in full_text_check or 
                    "НАРУЖУ" in full_text_check or 
                    re.search(r"FS\b", full_text_check) is not None or 
                    raw_formula_clean.upper().endswith("FS") 
                )

                # Normalize formula (take suffix after last space)
                # "82 Вид СНАРУЖИ на себя 4ИxН14x4М1xН14x4И" -> "4ИxН14x4М1xН14x4И"
                # Remove thickness from formula chunk if present
                raw_formula_no_thick = PDFParser.THICK_RE.sub("", raw_formula_clean).strip()

                # Normalize formula (take suffix after last space)
                # "82 Вид СНАРУЖИ на себя 4ИxН14x4М1xН14x4И" -> "4ИxН14x4М1xН14x4И"
                if " " in raw_formula_no_thick:
                    # Split by space
                    parts = raw_formula_no_thick.split(" ")
                    position_formula = parts[-1] # Default fallback
                    
                    # Look for the last part that contains 'x' or 'х' (Cyrillic)
                    # This handles cases like "Formula (40" where "(40" is not the formula
                    for part in reversed(parts):
                        if "x" in part.lower() or "х" in part.lower():
                            position_formula = part
                            break
                else:
                    position_formula = raw_formula_no_thick
                
                logger.info(f"Item {position_num}: Raw='{raw_formula_no_thick}', Parsed='{position_formula}', IsOutside={is_outside}")

                # Parse numbers
                try:
                    width = int(raw_width)
                    height = int(raw_height)
                    count = int(raw_count)
                    area = float(raw_area.replace(",", "."))
                    mass = float(raw_mass.replace(",", "."))
                except ValueError as e:
                    logger.warning(f"Error parsing numbers for item {position_num}: {e}")
                    continue

                items.append({
                    "position_num": position_num,
                    "position_formula": position_formula,
                    "position_raskl": layout,
                    "position_width": width,
                    "position_hight": height,
                    "position_count": count,
                    "position_area": area,
                    "position_mass": mass,
                    "is_oytside": is_outside,
                    "raw_formula": raw_formula_clean 
                })
                
                last_end = anchor.end()
        
        return items
