"""
parse_epubs.py
Parseia todos os epubs configurados e insere os dados no SQLite com FTS5.
Uso: python parse_epubs.py
"""

import json
import sqlite3
import re
from pathlib import Path
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup


CONFIG_PATH = Path("scripts/epub_config.json")
DB_PATH     = Path("database.db")

KNOWN_POVS = [
    'ARYA', 'BRAN', 'CATELYN', 'DAENERYS', 'EDDARD', 'JON', 'SANSA', 'TYRION',
    'THEON', 'DAVOS', 'JAIME', 'CERSEI', 'BRIENNE', 'SAMWELL', 'MELISANDRE',
    'VICTARION', 'PROLOGO', 'EPILOGO', 'PROFETA'
]

SKIP_PATTERNS = ['cover', 'toc', 'copyright', 'ficha', 'agradecimentos', 'tradutor', 'apendice', 'indice', 'nota']


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def should_skip_document(doc_filename: str) -> bool:
    fn_lower = doc_filename.lower()
    for pattern in SKIP_PATTERNS:
        if pattern in fn_lower:
            return True
    return False


def extract_pov(text: str) -> str:
    """Tenta extrair o nome do POV do início do texto."""
    if not text:
        return "Desconhecido"

    text_upper = text[:200].upper()

    for pov in KNOWN_POVS:
        if pov in text_upper:
            return pov.capitalize()

    # Fallback: pega primeiras palavras até encontrar algo reconhecível
    words = text.split()[:3]
    if words:
        first = words[0].capitalize()
        if len(first) > 2:
            return first

    return "Desconhecido"


def parse_book(book_config: dict) -> list[dict]:
    epub_path  = book_config["filename"]
    book_num   = book_config["book_number"]
    book_title = book_config["book_title"]

    print("\n[Parseando] " + book_title + " (" + epub_path + ")")

    book = epub.read_epub(epub_path)
    documents = list(book.get_items_of_type(ITEM_DOCUMENT))

    rows = []
    chapter_number = 0

    for doc in documents:
        if should_skip_document(doc.file_name):
            print("   [SKIP] Pulando: " + doc.file_name)
            continue

        soup = BeautifulSoup(doc.get_content(), "html.parser")

        text = soup.get_text(separator=" ", strip=True)
        if len(text) < 50:
            print("   [SKIP] Pulando (texto curto): " + doc.file_name)
            continue

        pov = extract_pov(text)

        paragraphs = [
            clean_text(p.get_text(separator=" ", strip=True))
            for p in soup.find_all("p")
            if clean_text(p.get_text(separator=" ", strip=True))
        ]

        if len(paragraphs) < 3:
            print("   [SKIP] Pulando (poucos parágrafos): " + doc.file_name)
            continue

        chapter_number += 1
        print("   [OK] Capítulo " + str(chapter_number).zfill(3) + " | POV: " + pov + " | " + str(len(paragraphs)) + " parágrafos")

        for idx, text in enumerate(paragraphs):
            rows.append({
                "book_number":     book_num,
                "book_title":      book_title,
                "chapter_number":  chapter_number,
                "chapter_title":   pov,
                "pov":             pov,
                "paragraph_index": idx,
                "text":            text,
            })

    print("   --> Total: " + str(chapter_number) + " capítulos, " + str(len(rows)) + " parágrafos")
    return rows


def create_database(db_path: Path):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS paragraphs;

        CREATE VIRTUAL TABLE paragraphs USING fts5(
            book_number,
            book_title,
            chapter_number,
            chapter_title,
            pov,
            paragraph_index,
            text,
            tokenize = 'unicode61'
        );
    """)

    conn.commit()
    return conn


def insert_rows(conn: sqlite3.Connection, rows: list[dict]):
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO paragraphs (
            book_number, book_title, chapter_number,
            chapter_title, pov, paragraph_index, text
        ) VALUES (
            :book_number, :book_title, :chapter_number,
            :chapter_title, :pov, :paragraph_index, :text
        )
    """, rows)
    conn.commit()


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    books  = config["books"]

    print("[DB] Criando banco de dados em " + str(DB_PATH) + "...")
    conn = create_database(DB_PATH)

    total_paragraphs = 0
    for book_config in books:
        rows = parse_book(book_config)
        insert_rows(conn, rows)
        total_paragraphs += len(rows)

    conn.close()

    print("\n[OK] Concluído!")
    print("   Banco: " + str(DB_PATH))
    print("   Total de parágrafos indexados: " + str(total_paragraphs))


if __name__ == "__main__":
    main()