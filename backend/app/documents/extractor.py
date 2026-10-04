from pathlib import Path
import pymupdf
from docx import Document


def extract_text(file_path: Path) -> str:
    """
    Extracts plain text from supported document types (.pdf, .docx, .txt, .md).
    Returns extracted text string. Safely catches file reading errors.
    """
    if not file_path.exists() or not file_path.is_file():
        return ""

    ext = file_path.suffix.lower()
    try:
        if ext == ".pdf":
            doc = pymupdf.open(file_path)
            try:
                pages_text = []
                for page in doc:
                    t = page.get_text()
                    if t:
                        pages_text.append(t)
                return "\n".join(pages_text)
            finally:
                doc.close()

        elif ext == ".docx":
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            return "\n".join(paragraphs)

        elif ext in [".txt", ".md"]:
            return file_path.read_text(encoding="utf-8", errors="ignore")

        return ""
    except Exception as err:
        print(f"Warning: Failed to extract text from '{file_path.name}': {err}")
        return ""
