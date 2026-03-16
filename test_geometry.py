import pdfplumber
from bot.services.pdf_parser import PDFParser
import logging

logging.basicConfig(level=logging.DEBUG)

file_path = "docs/examples/98-132-1036.pdf"
try:
    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        rows = PDFParser._group_words_into_rows(words)
        headers = PDFParser._find_table_headers(rows)
        print("HEADERS FOUND:", headers)
        for h in headers:
            print(f"Formula Left: {h['formula_left']}, Size Left: {h['size_left']}")
            
        items = PDFParser._parse_page_by_geometry(words)
        print("ITEMS FOUND:", len(items))
        for item in items:
            print("=====")
            print(item['position_num'])
            print("RAW FORMULA:", item['raw_formula'])
            print("PARSED:", item['position_formula'])
except Exception as e:
    print(f"Error: {e}")
