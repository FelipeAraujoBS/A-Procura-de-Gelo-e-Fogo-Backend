"""
inspect_epub.py
Inspeciona a estrutura interna de um epub e gera um relatório JSON.
Uso: python inspect_epub.py <caminho_do_epub>
"""

import sys
import json
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup


def inspect(epub_path: str) -> dict:
    book = epub.read_epub(epub_path)

    dc = book.metadata.get("http://purl.org/dc/elements/1.1/", {})
    title = dc.get("title", [("Desconhecido",)])[0]
    title = title[0] if isinstance(title, tuple) else title

    documents = list(book.get_items_of_type(ITEM_DOCUMENT))

    docs_info = []
    for i, doc in enumerate(documents):
        soup = BeautifulSoup(doc.get_content(), "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        heading = None
        heading_tag = None
        for tag in ["h1", "h2", "h3", "h4"]:
            el = soup.find(tag)
            if el:
                heading = el.get_text(strip=True)
                heading_tag = tag
                break

        all_headings = []
        for tag in ["h1", "h2", "h3", "h4"]:
            for el in soup.find_all(tag):
                all_headings.append({"tag": tag, "text": el.get_text(strip=True)})

        images_info = []
        for img in soup.find_all("img"):
            alt = img.get("alt", "")
            src = img.get("src", "")
            images_info.append({"alt": alt, "src": src})

        paragraph_count = len([p for p in soup.find_all("p") if p.get_text(strip=True)])

        docs_info.append({
            "index":           i,
            "file_name":       doc.file_name,
            "first_heading":   heading,
            "heading_tag":     heading_tag,
            "all_headings":    all_headings,
            "images":          images_info,
            "paragraph_count": paragraph_count,
            "text_preview":    text[:200].replace("\n", " ") if text else "",
            "char_count":      len(text),
        })

    return {
        "epub_path":      epub_path,
        "title":          title,
        "document_count": len(documents),
        "documents":      docs_info,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python inspect_epub.py <caminho_do_epub>")
        sys.exit(1)

    result = inspect(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))