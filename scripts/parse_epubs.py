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


ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
         "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX"]

TOC_SKIP_TITLES = {"start", "cover", "sumário", "sumario", "índice", "indice",
                   "créditos", "creditos", "ficha técnica", "ficha tecnica",
                   "sobre o autor", "sobre os organizadores", "sobre o organizador",
                   "folha de rosto", "conheça outros", "coleção", "colecao"}

def to_roman(n: int) -> str:
    return ROMAN[n] if n < len(ROMAN) else str(n)

# Build pattern to match any existing roman numeral suffix (I through XXX)
# Sort by length descending so longer numerals match first
_roman_suffixes = sorted([r for r in ROMAN if r], key=len, reverse=True)
ROMAN_SUFFIX_PATTERN = re.compile(r'\s+(?:' + '|'.join(_roman_suffixes) + r')$', re.IGNORECASE)


CONFIG_PATH = Path("scripts/epub_config.json")
ALIASES_PATH = Path("scripts/pov_aliases.json")
DB_PATH     = Path("database.db")

POV_ALIASES: dict = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))

KNOWN_POVS = [
    'ARYA', 'BRAN', 'CATELYN', 'DAENERYS', 'EDDARD', 'JON', 'SANSA', 'TYRION',
    'THEON', 'DAVOS', 'JAIME', 'CERSEI', 'BRIENNE', 'SAMWELL', 'MELISANDRE',
    'VICTARION', 'PROLOGO', 'EPILOGO', 'PROFETA'
]

SKIP_PATTERNS = ['cover', 'toc', 'copyright', 'ficha', 'agradecimentos', 'tradutor', 'apendice', 'indice', 'nota', 'capa', 'rosto', 'ficha']

def load_toc_ncx(epub_path: str) -> dict:
    """Carrega o arquivo toc.ncx e retorna um dicionário {filename: chapter_name}."""
    TOC_FILENAME_PATTERNS = [
        'index_split_',
        'split_',
        'part',
    ]
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
                fn_lower = filename.lower()
                matched = False
                for pat in TOC_FILENAME_PATTERNS:
                    if pat in fn_lower:
                        matched = True
                        break
                if not matched and (fn_lower.startswith('section') or '97885' in fn_lower):
                    matched = True
                if matched:
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


CANONICAL_NAMES = {
    "jaime": "Jaime",
    "cersei": "Cersei",
    "brienne": "Brienne",
    "samwell": "Samwell",
    "arya": "Arya",
    "sansa": "Sansa",
    "jon": "Jon",
    "tyrion": "Tyrion",
    "bran": "Bran",
    "daenerys": "Daenerys",
    "eddard": "Eddard",
    "theon": "Theon",
    "davos": "Davos",
    "mellisandre": "Melisandre",
    "melisandre": "Melisandre",
    "victarion": "Victarion Greyjoy",
}


def normalize_pov(raw_pov: str | None) -> str | None:
    """
    Normaliza o POV detectado:
    - Se for um alias conhecido, retorna o nome canônico
    - Se for um nome em maiúsculas, normaliza para o formato canônico
    - Se não for alias, retorna o valor original
    - Se for None, retorna None
    """
    if raw_pov is None:
        return None

    # Primeiro verifica se é um alias conhecido
    for alias, canonical in POV_ALIASES.items():
        if raw_pov.lower() == alias.lower():
            return canonical

    # Depois normaliza nomes canônicos (remove sufixos como I, II, III etc)
    base_name = re.sub(r'\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)$', '', raw_pov, flags=re.IGNORECASE)
    if base_name.lower() in CANONICAL_NAMES:
        return CANONICAL_NAMES[base_name.lower()]

    return raw_pov


def parse_book(book_config: dict) -> list[dict]:
    epub_path  = book_config["filename"]
    book_num   = book_config["book_number"]
    book_title = book_config["book_title"]
    has_pov    = book_config.get("has_pov", True)

    if not has_pov:
        return parse_book_nonpov(book_config)

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

        doc_filename = doc.file_name.split('/')[-1] if '/' in doc.file_name else doc.file_name

        if toc_map and len(toc_map) > 10 and doc_filename not in toc_map:
            continue

        raw_pov = extract_pov(first_para)

        if toc_map and doc_filename in toc_map:
            toc_name = toc_map[doc_filename]
            if toc_name and not any(skip in toc_name.lower() for skip in ['agrad', 'nota', 'apêndice', 'mapa', 'crédito', 'autor']):
                raw_pov = toc_name
                chapter_title = toc_name

        skip_keywords = ["casa ", "os ", "a ", "nota", "agrad", "epilogo", "prologo", "prólogo", "epílogo", "ficha", "capa", "copyright", "table", "nossos", "isto"]
        if len(raw_pov) <= 2 or any(raw_pov.lower().startswith(kw) for kw in skip_keywords):
            continue

        pov = normalize_pov(raw_pov)

        if not pov:
            if any(w in chapter_title.lower() for w in ["prólogo", "prologo"]):
                pov = "Prólogo"
            elif any(w in chapter_title.lower() for w in ["epílogo", "epilogo"]):
                pov = "Epílogo"
            else:
                pov = "Desconhecido"
                print(f"   [WARNING] POV nao identificado: {doc_filename}")

        remaining_paragraphs = all_paragraphs[1:]

        if len(remaining_paragraphs) < 2:
            continue

        chapter_number += 1
        print(f"   [OK] Cap. {chapter_number:03d} | POV: {pov:<25} | {len(remaining_paragraphs)} paragrafos")

        theon_dany_split = None
        if pov == "Theon":
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
                    "pov":             pov,
                    "paragraph_index": idx,
                    "text":            text,
                })
            dany_paragraphs = remaining_paragraphs[theon_dany_split:]
            chapter_number += 1
            print(f"   [OK] Cap. {chapter_number:03d} | POV: Daenerys              | {len(dany_paragraphs)} paragrafos")
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
                    "pov":             pov,
                    "paragraph_index": idx,
                    "text":            text,
                })

    print("   --> Total: " + str(chapter_number) + " capítulos, " + str(len(rows)) + " parágrafos")
    return rows


def parse_book_nonpov(book_config: dict) -> list[dict]:
    """Parseia livros sem POV:
       - Agrupa documentos consecutivos não-TOC no grupo TOC anterior.
       - Grupos TOC pequenos (<= min_pars) são "title cards": mesclam com o
         grupo seguinte e emprestam seu titulo.
    """
    epub_path  = book_config["filename"]
    book_num   = book_config["book_number"]
    book_title = book_config["book_title"]
    min_pars   = book_config.get("min_paragraphs", 3)

    print("\n[Parseando] " + book_title + " (" + epub_path + ")")

    toc_map = load_toc_ncx(epub_path)
    if toc_map:
        print(f"   [TOC] Carregados {len(toc_map)} itens do toc.ncx")

    book = epub.read_epub(epub_path)
    documents = list(book.get_items_of_type(ITEM_DOCUMENT))

    # Phase 1: collect all paragraphs, group consecutive non-TOC into preceding TOC group
    # groups = [{"toc": str|None, "paras": [str]}]
    groups = []
    for doc in documents:
        if should_skip_document(doc.file_name):
            continue

        soup = BeautifulSoup(doc.get_content(), "html.parser")
        all_paragraphs = [
            clean_text(p.get_text(separator=" ", strip=True))
            for p in soup.find_all("p")
            if clean_text(p.get_text(separator=" ", strip=True))
        ]

        if len(all_paragraphs) < 2:
            continue

        doc_filename = doc.file_name.split('/')[-1] if '/' in doc.file_name else doc.file_name
        raw_toc = toc_map.get(doc_filename)

        has_toc = raw_toc is not None
        clean_toc = None
        if raw_toc and len(raw_toc) > 2 and raw_toc.lower() not in TOC_SKIP_TITLES:
            clean_toc = raw_toc

        if has_toc:
            groups.append({"toc": clean_toc, "paras": list(all_paragraphs)})
        else:
            if groups:
                groups[-1]["paras"].extend(all_paragraphs)
            else:
                groups.append({"toc": None, "paras": list(all_paragraphs)})

    # Phase 2: merge small TOC groups ("title cards") with the next group
    merged = []
    i = 0
    while i < len(groups):
        g = groups[i]
        if g["toc"] and len(g["paras"]) <= min_pars and i + 1 < len(groups):
            nxt = groups[i + 1]
            g["paras"].extend(nxt["paras"])
            merged.append(g)
            i += 2
        else:
            merged.append(g)
            i += 1

    # Phase 3: orphan groups without toc merge into the preceding group
    final = []
    for g in merged:
        if g["toc"]:
            final.append(g)
        else:
            if final:
                final[-1]["paras"].extend(g["paras"])
            else:
                final.append(g)

    # Phase 4: create chapters
    rows = []
    chapter_number = 0
    for g in final:
        paras = g["paras"]
        toc   = g["toc"]
        if len(paras) < min_pars:
            continue

        chapter_number += 1
        if toc:
            chapter_title = toc
            remaining = paras
        else:
            chapter_title = paras[0]
            remaining = paras[1:]

        if len(remaining) < 1:
            continue

        print(f"   [OK] Cap. {chapter_number:03d} | (sem POV)               | {len(remaining)} paragrafos")

        for idx, text in enumerate(remaining):
            rows.append({
                "book_number":     book_num,
                "book_title":      book_title,
                "chapter_number":  chapter_number,
                "chapter_title":   chapter_title,
                "pov":             None,
                "paragraph_index": idx,
                "text":            text,
            })

    print(f"   --> Total: {chapter_number} capítulos, {len(rows)} parágrafos")
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


def strip_roman_suffix(name: str) -> str:
    return ROMAN_SUFFIX_PATTERN.sub('', name).strip()


def assign_roman_numerals(rows: list[dict]) -> list[dict]:
    """Post-processa os rows atribuindo numeração romana aos títulos dos capítulos com POV.
       Incrementa o contador UMA vez por capítulo, não por parágrafo."""
    current: dict[tuple[int, str], int] = {}
    seen: set[tuple[int, str, int]] = set()
    result = []
    for row in rows:
        pov = row.get("pov")
        if pov and pov.lower() not in ("prólogo", "prologo", "epílogo", "epilogo"):
            clean_pov = strip_roman_suffix(pov)
            key = (row["book_number"], clean_pov)
            ch_key = (row["book_number"], clean_pov, row["chapter_number"])
            if ch_key not in seen:
                seen.add(ch_key)
                current[key] = current.get(key, 0) + 1
            row["chapter_title"] = f"{clean_pov} {to_roman(current[key])}"
        result.append(row)

    return result


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    books  = config["books"]

    print("[DB] Criando banco de dados em " + str(DB_PATH) + "...")
    conn = create_database(DB_PATH)

    total_paragraphs = 0
    for book_config in books:
        rows = parse_book(book_config)
        rows = assign_roman_numerals(rows)
        insert_rows(conn, rows)
        total_paragraphs += len(rows)

    conn.close()

    print("\n[OK] Concluído!")
    print("   Banco: " + str(DB_PATH))
    print("   Total de parágrafos indexados: " + str(total_paragraphs))


if __name__ == "__main__":
    main()