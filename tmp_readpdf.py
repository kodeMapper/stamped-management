import PyPDF2
from pathlib import Path

path = Path("IP Project report.pdf")
reader = PyPDF2.PdfReader(str(path))
text_path = Path("report_extract.txt")
with text_path.open("w", encoding="utf-8") as f:
    for idx, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        f.write(f"\n--- PAGE {idx} ---\n")
        f.write(text)
print("Extracted to", text_path)
