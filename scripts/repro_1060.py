import sys
import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, or_
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.services.pdf_parser import PDFParser
from bot.services.analyzer import Analyzer
from bot.database.models import SizeControl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB Config
load_dotenv()
DB_DSN = os.environ["DB_DSN"]

async def test_repro_1060():
    file_path = "docs/examples/00-134-1060.pdf"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Extracting text from {file_path}...")
    try:
        text = PDFParser.extract_text(file_path)
        print("--- Text Snippet ---")
        print(text[:500])
        print("--------------------")

        items = PDFParser.parse_text(text)
        
        target_item = None
        # User said item name contains "KALEVA ALUVET FS"
        # Or formula "4М1хН14х4М1хН6х4LHBalance"
        
        for item in items:
            raw = item.get("raw_formula", "")
            pos = item.get("position_num", "")
            if "LHBalance" in raw or "KALEVA" in pos:
                target_item = item
                break
        
        if not target_item:
            print("Target item NOT FOUND")
            return

        print(f"\n[MATCH FOUND]")
        print(f"Position: {target_item.get('position_num')}")
        print(f"Raw Formula Chunk: '{target_item.get('raw_formula')}'") # This is cleaned formula
        print(f"Position Formula: '{target_item.get('position_formula')}'")
        print(f"Is Outside: {target_item.get('is_oytside')}")
        print(f"Width: {target_item.get('position_width')}")
        print(f"Height: {target_item.get('position_hight')}")
        
        # Connect to DB to check rule
        engine = create_async_engine(DB_DSN)
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with async_session() as session:
            analyzer = Analyzer(session)
            await analyzer.load_films()
            
            # Parse Formula
            elements = analyzer.parse_formula(target_item["position_formula"], target_item["is_oytside"])
            print(f"\nParsed Elements (is_outside={target_item['is_oytside']}):")
            for e in elements:
                print(e)
            
            # Check Slip Logic
            w = target_item["position_width"]
            h = target_item["position_hight"]
            
            w_round = analyzer._round_size(w)
            h_round = analyzer._round_size(h)
            print(f"\nRounded Size: {w_round}x{h_round}")
            
            # Fetch Rule
            stmt = select(SizeControl).where(
                or_(
                    and_(SizeControl.dim1 == w_round, SizeControl.dim2 == h_round),
                    and_(SizeControl.dim1 == h_round, SizeControl.dim2 == w_round)
                )
            ).limit(1)
            result = await session.execute(stmt)
            rule = result.scalars().first()
            
            if rule:
                print(f"\nRule Found: ID={rule.id}")
                print(f"Formula 1k: {rule.formula_1_1k} / {rule.formula_2_1k}")
                print(f"Formula 2k: {rule.formula_1_2k} / {rule.formula_2_2k}")
                print(f"Formula 3k: {rule.formula_1_3k} / {rule.formula_2_3k}")
                
                # Check actual thicknesses length vs rule length
                print(f"Actual Thicknesses: {[e['thickness'] for e in elements]}")
                
                # Run check_slip manually
                errors = await analyzer.check_slip(w, h, elements)
                print(f"\nCheck Slip Errors: {errors}")
            else:
                print(f"\nNO Rule Found for {w_round}x{h_round}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_repro_1060())
