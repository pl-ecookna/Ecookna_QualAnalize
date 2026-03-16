import pdfplumber
from bot.services.pdf_parser import PDFParser
import re

file_path = "docs/examples/98-132-1036.pdf"
try:
    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        rows = PDFParser._group_words_into_rows(words)
        headers = PDFParser._find_table_headers(rows)
        current_header = headers[0]
        for row in rows:
            for word in row["words"]:
                text = PDFParser._word_text(word)
                if PDFParser.NUMBER_RE.fullmatch(text):
                    print("Matches NUMBER_RE:", text)
                    print("x1:", float(word["x1"]), "formula_left:", current_header["formula_left"])
except Exception as e:
    print(f"Error: {e}")
