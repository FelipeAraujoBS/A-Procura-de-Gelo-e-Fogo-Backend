"""
parse_epubs.py
Parseia todos os epubs configurados e insere os dados no SQLite com FTS5.
Uso: python parse_epubs.py
"""

import json
import sqlite3
import re
import zipfile
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

SKIP_PATTERNS = ['cover', 'toc', 'copyright', 'ficha', 'agradecimentos', 'tradutor', 'apendice', 'indice', 'nota', 'capa', 'rosto', 'ficha']

def load_toc_ncx(epub_path: str) -> dict:
    """Carrega o arquivo toc.ncx e retorna um dicionário {filename: chapter_name}."""
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            toc_files = [f for f in z.namelist() if 'toc.ncx' in f.lower()]
            if not toc_files:
                return {}
            toc_path = toc_files[0]
            content = z.read(toc_path).decode('utf-8')
            pattern = r'<navLabel>\s*<text>([^<]+)</text>\s*</navLabel>\s*<content src="([^"]+)"'
            matches = re.findall(pattern, content)
            toc_map = {}
            for name, src in matches:
                filename = src.split('/')[-1]
                if '#' in filename:
                    filename = filename.split('#')[0]
                if 'index_split_' in filename or filename.startswith('Section') or '97885' in filename:
                    toc_map[filename] = name.strip()
            return toc_map
    except Exception as e:
        print(f"   [AVISO] Não foi possível ler toc.ncx: {e}")
    return {}


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

    text_stripped = text.strip()
    text_upper = text_stripped.upper()
    first_word = text_stripped.split()[0].upper() if text_stripped.split() else ""

    for pov in KNOWN_POVS:
        if text_upper.startswith(pov + " ") or text_upper.startswith(pov):
            return pov.capitalize()

    if first_word in KNOWN_POVS:
        return first_word.capitalize()

    if first_word:
        return first_word.capitalize()

    return "Desconhecido"


def parse_book(book_config: dict) -> list[dict]:
    epub_path  = book_config["filename"]
    book_num   = book_config["book_number"]
    book_title = book_config["book_title"]

    print("\n[Parseando] " + book_title + " (" + epub_path + ")")

    toc_map = load_toc_ncx(epub_path)
    if toc_map:
        print(f"   [TOC] Carregados {len(toc_map)} capítulos do toc.ncx")

    book = epub.read_epub(epub_path)
    documents = list(book.get_items_of_type(ITEM_DOCUMENT))

    rows = []
    chapter_number = 0

    for doc in documents:
        if should_skip_document(doc.file_name):
            continue

        soup = BeautifulSoup(doc.get_content(), "html.parser")

        all_paragraphs = [
            clean_text(p.get_text(separator=" ", strip=True))
            for p in soup.find_all("p")
            if clean_text(p.get_text(separator=" ", strip=True))
        ]

        if len(all_paragraphs) < 3:
            continue

        first_para = all_paragraphs[0]
        chapter_title = first_para.strip()
        first_pov = extract_pov(first_para)

        doc_filename = doc.file_name.split('/')[-1] if '/' in doc.file_name else doc.file_name

        if toc_map and len(toc_map) > 10 and doc_filename not in toc_map:
            continue

        if toc_map and doc_filename in toc_map:
            toc_name = toc_map[doc_filename]
            if toc_name and not any(skip in toc_name.lower() for skip in ['agrad', 'nota', 'apêndice', 'mapa', 'crédito', 'autor']):
                first_pov = toc_name
                chapter_title = toc_name

        skip_keywords = ["casa ", "os ", "a ", "nota", "agrad", "epilogo", "prologo", "prólogo", "epílogo", "ficha", "capa", "copyright", "table", "nossos", "isto"]
        if len(first_pov) <= 2 or any(first_pov.lower().startswith(kw) for kw in skip_keywords):
            continue

        remaining_paragraphs = all_paragraphs[1:]

        if len(remaining_paragraphs) < 2:
            continue

        chapter_number += 1
        print(f"   [OK] Capítulo {chapter_number:03d} | POV: {first_pov} | {len(remaining_paragraphs)} parágrafos")

        theon_dany_split = None
        if first_pov == "Theon":
            for i, p in enumerate(remaining_paragraphs):
                if p.strip().startswith("Daenerys") and len(remaining_paragraphs) - i > 10:
                    theon_dany_split = i
                    break

        if theon_dany_split:
            for idx, text in enumerate(remaining_paragraphs[:theon_dany_split]):
                rows.append({
                    "book_number":     book_num,
                    "book_title":      book_title,
                    "chapter_number":  chapter_number,
                    "chapter_title":   chapter_title,
                    "pov":             first_pov,
                    "paragraph_index": idx,
                    "text":            text,
                })
            dany_paragraphs = remaining_paragraphs[theon_dany_split:]
            chapter_number += 1
            print(f"   [OK] Capítulo {chapter_number:03d} | POV: Daenerys | {len(dany_paragraphs)} parágrafos")
            for idx, text in enumerate(dany_paragraphs):
                rows.append({
                    "book_number":     book_num,
                    "book_title":      book_title,
                    "chapter_number":  chapter_number,
                    "chapter_title":   "Daenerys",
                    "pov":             "Daenerys",
                    "paragraph_index": idx,
                    "text":            text,
                })
        else:
            for idx, text in enumerate(remaining_paragraphs):
                rows.append({
                    "book_number":     book_num,
                    "book_title":      book_title,
                    "chapter_number":  chapter_number,
                    "chapter_title":   chapter_title,
                    "pov":             first_pov,
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