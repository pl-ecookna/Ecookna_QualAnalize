import pdfplumber
from bot.services.pdf_parser import PDFParser

file_path = "docs/examples/98-132-1036.pdf"
try:
    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        rows = PDFParser._group_words_into_rows(words)
        headers = PDFParser._find_table_headers(rows)
        current_header = headers[0]
        
        current_rows = []
        for row in rows:
            if row["top"] <= current_header["bottom"]:
                continue
            has_number = any(
                PDFParser.NUMBER_RE.fullmatch(PDFParser._word_text(word))
                and float(word["x1"]) <= current_header["formula_left"]
                for word in row["words"]
            )
            if has_number:
                if current_rows:
                    item = PDFParser._parse_item_from_rows(current_rows, current_header["formula_left"], current_header["size_left"])
                    print("ITEM 1:", item)
                    break
                current_rows = [row]
            elif current_rows:
                current_rows.append(row)
        
        if current_rows:
            item = PDFParser._parse_item_from_rows(current_rows, current_header["formula_left"], current_header["size_left"])
            print("ITEM FIN:", item)
except Exception as e:
    print(f"Error: {e}")
