import logging
from bot.services.pdf_parser import PDFParser
import sys

logging.basicConfig(level=logging.DEBUG)

file_path = "docs/examples/98-132-1036.pdf"
try:
    text = PDFParser.extract_text(file_path)
    res = PDFParser.parse_text(text)
    for r in res:
        print(r['position_num'], "->", r['position_formula'])
except Exception as e:
    print(f"Error: {e}")
