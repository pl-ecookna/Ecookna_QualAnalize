import logging
import re
from typing import List, Optional, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Film, SizeControl, QualPos, QualIssue
from bot.config import settings
from bot.services.directus import DirectusClient

logger = logging.getLogger(__name__)

FORMULA_SPLIT_RE = re.compile(r"(?<=[0-9A-Za-zА-Яа-я.,])[xх](?=[0-9A-Za-zА-Яа-я])")
TEMPERED_FORMULA_RE = re.compile(r"зак(?![а-яёА-ЯЁ])", re.IGNORECASE)

class Analyzer:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._films_cache: dict = {}
        self._articles_cache: dict = {}
        self.directus = DirectusClient(base_url=settings.DIRECTUS_URL, token=settings.DIRECTUS_TOKEN, verify_ssl=False)

    async def load_films(self):
        """Loads films from Directus to cache dict."""
        try:
            response = await self.directus.get_items("films", params={"limit": -1})
            data = response.get("data", [])
            for item in data:
                if item.get("films_article"):
                    article = item["films_article"].strip()
                    film_type = item.get("type_of_film", "")
                    if not film_type:
                        film_type = item.get("films_type", "")
                    self._films_cache[article] = film_type
            logger.info(f"Loaded {len(self._films_cache)} films from Directus.")
        except Exception as e:
            logger.error(f"Failed to load films from Directus: {e}")

    async def load_articles(self):
        """Loads articles from Directus to cache."""
        try:
            response = await self.directus.get_items("art_rules", params={"limit": -1})
            data = response.get("data", [])
            for item in data:
                if item.get("glass_article"):
                    # Cache by article name
                    self._articles_cache[item["glass_article"].strip()] = item
            logger.info(f"Loaded {len(self._articles_cache)} articles from Directus.")
        except Exception as e:
            logger.error(f"Failed to load articles from Directus: {e}")

    def get_thickness(self, p: str) -> Tuple[int, bool]:
        """Extracts thickness and determines if it's a triplex from article string."""
        # For triplex, e.g. 3.3.1, sum first two digits
        triplex_match = re.search(r"(\d+)\.(\d+)\.\d+", p)
        if triplex_match:
            return int(triplex_match.group(1)) + int(triplex_match.group(2)), True
            
        # Standard thickness extraction
        match = re.search(r"(\d+)", p)
        return (int(match.group(1)), False) if match else (0, False)

    def _is_tempered_article(self, article: str) -> bool:
        """Tempering is identified only by `з`/`зак` in the formula after glass thickness."""
        return bool(TEMPERED_FORMULA_RE.search(article))

    def parse_formula(self, formula: str, is_outside: bool) -> List[dict]:
        """
        Parses formula into elements, filters films, and handles 'is_outside' order.
        Returns list of dict: {'article': str, 'type': 'glass'|'frame', 'thickness': int}
        """
        if not formula:
            return []
        
        # Split only real formula separators, not incidental letters inside service text.
        raw_parts = FORMULA_SPLIT_RE.split(formula)
        elements = []
        
        pending_triplex_film = False

        for part in raw_parts:
            article = part.strip()
            if not article:
                continue

            # Filter Films
            # Normalize article for film check (remove spaces for cases like "СМАР Т")
            article_norm = article.replace(" ", "")
            if article in self._films_cache or article_norm in self._films_cache:
                film_type = self._films_cache.get(article) or self._films_cache.get(article_norm)
                if film_type and film_type.lower() == "для триплекса":
                    pending_triplex_film = True
                continue

            # Determine type (Glass vs Frame)
            # Logic from SQL: ^[HWНШ] -> frame, else glass
            # Also common sense: frames usually start with letters indicating spacer
            is_frame = bool(re.match(r"^[HWНШ]", article, re.IGNORECASE) or re.search(r"^[A-Za-z]+[HWНШ]\d+", article, re.IGNORECASE))
            etype = "frame" if is_frame else "glass"
            
            thickness, is_triplex = self.get_thickness(article)
            
            is_tempered = False
            if etype == "glass":
                # Проверка на маркеры закалки в строке
                if self._is_tempered_article(article):
                    is_tempered = True
                
                # Проверка в кэше статей (существующая логика)
                if not is_tempered and article in self._articles_cache:
                    processing = self._articles_cache[article].get("type_of_processing", "")
                    if processing and processing.lower() == "закаленное":
                        is_tempered = True
            
            new_element = {
                "article": article,
                "type": etype,
                "thickness": thickness,
                "is_triplex": is_triplex,
                "is_tempered": is_tempered
            }
            
            if etype == "glass" and pending_triplex_film and elements:
                # Merge with the previous glass
                prev_element = elements.pop()
                if prev_element["type"] == "glass":
                    new_element["article"] = f"{prev_element['article']} + {article}"
                    new_element["thickness"] += prev_element["thickness"]
                    new_element["is_triplex"] = True
                    # If either was tempered, the triplex is considered tempered (for validation logic)
                    new_element["is_tempered"] = new_element["is_tempered"] or prev_element["is_tempered"]
                else:
                    # In case the previous element wasn't a glass, just put it back
                    elements.append(prev_element)
                
                pending_triplex_film = False
                
            elements.append(new_element)
        
        # If is_outside, reverse the elements order
        # Requirement: "Outside -> Inside" normalization
        # If formula is given as "Inside -> Outside" (standard), and is_outside=True, 
        # it means the string we see is actually "Outside -> Inside"? 
        # Wait, let's re-read the SQL logic I wrote earlier:
        # IF v_is_outside THEN
        #   SELECT array_agg(elem ORDER BY nr DESC) ...
        # END IF;
        # Since standard formulas are typically listed Outer->Inner (or vice versa depending on factory),
        # but the check logic expects [Glass1, Frame1, Glass2...].
        # The user said: "when is_outside is true, reverse the formula order"
        # So we do exactly that.
        if is_outside:
            elements.reverse()
            
        return elements

    def _round_size(self, value: int) -> int:
        """
        Rounds size to nearest 100 with threshold 51.
        Logic from trg_calc_qual_pos:
        (val / 100) * 100 + (100 if val % 100 >= 51 else 0)
        """
        base = (value // 100) * 100
        remainder = value % 100
        return base + 100 if remainder >= 51 else base

    def _calc_cam_count(self, formula: str) -> int:
        """
        Calculates chamber count based on regex count of 'xH', 'xW' etc.
        Logic: regexp_count(formula, '[xх][нНhHwW]')
        """
        if not formula:
            return 0
        return len(re.findall(r"[xх][нНhHwW]", formula, re.IGNORECASE))

    def get_formula_total_thickness(self, formula: Optional[str]) -> Optional[int]:
        """
        Calculates total glazing unit thickness from a slip formula like `4-16-4`
        or `6-16-6-14-4` by summing all numeric segments, including spacers.
        """
        if not formula:
            return None

        cleaned = re.sub(r"\s{2,}", " ", formula.strip())
        if not cleaned:
            return None

        normalized = re.sub(r"[^0-9-]", "", cleaned)
        if not normalized:
            return None

        tokens = [token for token in normalized.split("-") if token]
        if not tokens:
            return None

        numeric_tokens = [int(token) for token in tokens if token.isdigit()]
        if not numeric_tokens:
            return None

        return sum(numeric_tokens)

    def has_spacer(self, formula: str) -> bool:
        """
        Returns True if formula contains a spacer frame marker (xH/xW/xН/..).
        """
        if not formula:
            return False
        return bool(re.search(r"[xх][нНhHwW]", formula, re.IGNORECASE))

    async def _find_size_control_rule(self, width: int, height: int) -> Tuple[Optional[SizeControl], int, int]:
        """Returns matching size_control rule with rounded dimensions."""
        w_round = self._round_size(width)
        h_round = self._round_size(height)

        stmt = select(SizeControl).where(
            or_(
                and_(SizeControl.dim1 == w_round, SizeControl.dim2 == h_round),
                and_(SizeControl.dim1 == h_round, SizeControl.dim2 == w_round)
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first(), w_round, h_round

    async def get_slip_formulas_by_size(self, width: int, height: int) -> dict:
        """
        Returns all available slip formulas for the provided dimensions.
        Result is grouped by camera count and uses the same size rounding as validation.
        """
        rule, w_round, h_round = await self._find_size_control_rule(width, height)

        if not rule:
            return {
                "found": False,
                "width": width,
                "height": height,
                "width_round": w_round,
                "height_round": h_round,
                "marking": None,
                "formulas": {},
                "formula_details": {}
            }

        formulas = {
            "1k": [value for value in [rule.formula_1_1k, rule.formula_2_1k] if value],
            "2k": [value for value in [rule.formula_1_2k, rule.formula_2_2k] if value],
            "3k": [value for value in [rule.formula_1_3k, rule.formula_2_3k] if value],
        }
        formula_details = {
            key: [
                {
                    "formula": formula,
                    "total_thickness": self.get_formula_total_thickness(formula),
                }
                for formula in values
            ]
            for key, values in formulas.items()
        }

        return {
            "found": True,
            "width": width,
            "height": height,
            "width_round": w_round,
            "height_round": h_round,
            "marking": rule.marking,
            "formulas": formulas,
            "formula_details": formula_details,
        }

    async def check_slip(self, width: int, height: int, formula_elements: List[dict]) -> List[str]:
        """
        Validates the formula against size_control table.
        Returns a list of error strings.
        """
        errors = []
        
        # 0. Round dimensions
        w_round = self._round_size(width)
        h_round = self._round_size(height)
        
        # 1. Provide formula elements
        if not formula_elements:
            return ["Пустая формула"]

        # 2. Calculate Cam Count
        # We need the original formula string for this, usually. 
        # But we can reconstruct or pass it. 
        # Ideally check_slip receives the FULL item or we calc it before.
        # Let's assume we can calc it from the elements types? 
        # No, 'xH' implies Spacer. An element with type 'frame' is a Spacer.
        # Let's count 'frame' elements from parsed list.
        # Actually SQL uses regex on string. Let's trust SQL logic is better matching spacers.
        # But here we don't have the string passed easily unless we change signature.
        # Let's change signature? Or just use frames count.
        # SQL: `regexp_count(..., '[xх][нНhHwW]')`. H/W/N are spacers.
        # My parsed elements 'type'='frame' is based on `^[HWНШ]`. Matches perfectly.
        cam_count = sum(1 for e in formula_elements if e["type"] == "frame")
        
        # 3. Find matching rule
        rule, _, _ = await self._find_size_control_rule(width, height)
        
        if not rule:
            return [f"Не найдено правило слипания для размера {w_round}x{h_round}"]

        # 4. Select Formulas based on Cam Count
        f1_text = None
        f2_text = None
        
        if cam_count == 0:
            return [] # No slip check for single glass / panels

        if cam_count == 1:
            f1_text = rule.formula_1_1k
            f2_text = rule.formula_2_1k
        elif cam_count == 2:
            f1_text = rule.formula_1_2k
            f2_text = rule.formula_2_2k
        elif cam_count == 3:
            f1_text = rule.formula_1_3k
            f2_text = rule.formula_2_3k
        
        if not f1_text and not f2_text:
             return [f"Не найдены допустимые формулы для {cam_count}-камерного пакета в правиле {w_round}x{h_round}"]

        valid_options = []
        if f1_text: valid_options.append(self._parse_rule_string(f1_text))
        if f2_text: valid_options.append(self._parse_rule_string(f2_text))
        
        match_found = False
        for opt in valid_options:
            if len(formula_elements) == len(opt):
                option_passes = True
                for act_el, exp_el in zip(formula_elements, opt):
                    act_thick = act_el["thickness"]
                    act_trip = act_el.get("is_triplex", False)
                    act_temp = act_el.get("is_tempered", False)
                    exp_thick = exp_el["thickness"]
                    exp_temp = exp_el["is_tempered"]
                    
                    # Spacer frames matching logic
                    if act_el["type"] == "frame":
                        if act_thick < exp_thick:
                            option_passes = False
                            break
                        continue

                    # Glass and Triplex matching logic
                    if act_trip:
                        if act_thick < exp_thick + 2:
                            option_passes = False
                            break
                        if exp_temp:
                            # If rule explicitly requires tempered glass, but we have triplex
                            # Current logic says triplex can't replace tempered? 
                            # Let's check the condition again: if exp_temp: option_passes = False
                            # This means if rule asks for '4з' we can't use '3.3.1'.
                            option_passes = False
                            break
                    else:
                        if act_thick < exp_thick:
                            option_passes = False
                            break
                        if exp_temp and not act_temp:
                            # Rule requires tempered, but order has raw (or generic) glass
                            option_passes = False
                            break
                        
                if option_passes:
                    match_found = True
                    break
        
        if not match_found:
             # Generate specific mismatch details avoiding "Mismatch!" title if possible, or make it descriptive
             # We compare against the first valid option as primary reference
             primary_opt = valid_options[0]
             
             details = []
             # Check lengths first
             limit = min(len(formula_elements), len(primary_opt))
             
             for i in range(limit):
                 act_el = formula_elements[i]
                 exp_el = primary_opt[i]
                 
                 act = act_el["thickness"]
                 act_trip = act_el.get("is_triplex", False)
                 act_temp = act_el.get("is_tempered", False)
                 exp = exp_el["thickness"]
                 exp_temp = exp_el["is_tempered"]
                 
                 reasons = []
                 
                 if act_el["type"] == "frame":
                     if act < exp:
                         reasons.append(f"{act} мм (в заказе) < {exp} мм (норма)")
                 else:
                     if act_trip:
                         if act < exp + 2:
                             reasons.append(f"{act} мм (в заказе) < {exp} мм + 2 мм (норма)")
                         if exp_temp:
                             reasons.append("триплексом нельзя заменять закаленное стекло")
                     else:
                         if act < exp:
                             reasons.append(f"{act} мм (в заказе) < {exp} мм (норма)")
                         if exp_temp and not act_temp:
                             reasons.append("требуется закалка")
                 
                 if reasons:
                     if len(reasons) > 1:
                         reason = f"{reasons[0]}; дополнительно: {'; '.join(reasons[1:])}"
                     else:
                         reason = reasons[0]
                     # Determine element name
                     el_type = act_el['type']
                     # Count index of this type
                     cnt = sum(1 for x in formula_elements[:i+1] if x['type'] == el_type)
                     
                     if el_type == 'glass':
                         type_name = "стекло"
                         suffix = "-е"
                         if cnt == 3: suffix = "-е" 
                         name_str = f"{cnt}{suffix} {type_name}"
                     else:
                         type_name = "рамка"
                         suffix = "-я"
                         if cnt == 3: suffix = "-я" 
                         name_str = f"{cnt}{suffix} {type_name}"
                     
                     if act_trip:
                         details.append(f"{name_str} (триплекс): {reason}")
                     else:
                         details.append(f"{name_str}: {reason}")
             
             # If details is empty but match_found is False, it implies logic error or length mismatch?
             # Or maybe it failed against primary_opt but passed against another? No, we checked all.
             # If details empty here, it means for primary_opt everything is >=. 
             # But we are here because NO option was fully >=.
             # So primary_opt MUST have some < failures OR length mismatch.
             
             if details:
                 # Construct message
                 msg = "Обнаружено несоответствие:\n"
                 msg += "\n".join([f"❌ {d}" for d in details]) + "\n"
                 
                 msg += f"\nФормула из заказа: {[str(e['thickness']) + ('зак' if e.get('is_tempered') else '') for e in formula_elements]}\n"
                 
                 def format_opt(opt_list):
                     return "/".join(f"{el['thickness']}{'з' if el['is_tempered'] else ''}" for el in opt_list)

                 if len(valid_options) > 1:
                     for i, opt in enumerate(valid_options, 1):
                         msg += f"Формула по таблице слипаемости {i}: {format_opt(opt)}\n"
                 else:
                     msg += f"Формула по таблице слипаемости: {format_opt(valid_options[0])}"

                 errors.append(msg)

        return errors

    def _parse_rule_string(self, rule_str: str) -> List[dict]:
        """
        Parses rule strings like '4/12/4', '6з/16/6з/14/6з', '6 з 16 6з', '6зак-16-6'
        into ordered dicts with tempered flag.
        """
        if not rule_str:
            return []

        pattern = re.compile(r"(\d+)\s*(зак|з)?", re.IGNORECASE)
        result = []

        for m in pattern.finditer(rule_str):
            thickness = int(m.group(1))
            is_tempered = bool(m.group(2))
            result.append({"thickness": thickness, "is_tempered": is_tempered})

        return result
