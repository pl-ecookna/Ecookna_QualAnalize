import pdfplumber
with pdfplumber.open("docs/examples/98-132-1036.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"--- Page {i+1} ---")
        print(page.extract_text())
