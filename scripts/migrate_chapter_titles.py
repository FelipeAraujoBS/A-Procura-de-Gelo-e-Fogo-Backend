"""
migrate_chapter_titles.py
Adiciona numeração romana aos títulos dos capítulos com POV.
Ex: "Bran" vira "Bran I", "Catelyn" vira "Catelyn I", etc.
Uso: python scripts/migrate_chapter_titles.py
"""

import sqlite3
import re
from pathlib import Path

DB_PATH = Path("database.db")

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
         "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX"]

def to_roman(n: int) -> str:
    return ROMAN[n] if n < len(ROMAN) else str(n)

# Build pattern to match any roman numeral suffix (I through XXX)
# Sort by length descending so longer numerals match first
_roman_suffixes = sorted([r for r in ROMAN if r], key=len, reverse=True)
ROMAN_PATTERN = re.compile(r'\s+(?:' + '|'.join(_roman_suffixes) + r')$', re.IGNORECASE)

def strip_roman_suffix(name: str) -> str:
    return ROMAN_PATTERN.sub('', name).strip()

# POVs que nao sao personagens reais - nao devem receber numeracao
NON_POV_PATTERNS = [
    r'^O Rei\b', r'^O REI\b', r'^Rei das Ilhas\b', r'^REI DAS ILHAS',
    r'^Prólogo', r'^Prologo', r'^Epílogo', r'^Epilogo',
    r'^Desconhecido',
    r'^Uma observação',
    r'^Para lá da muralha', r'^Na antiga Volantis', r'^Na Baía dos Escravos',
    r'^Em Bravos', r'^EM BRAVOS', r'^ENQUANTO ISSO',
    r'^SENHORES MENORES', r'^FORAS DA LEI', r'^IRMÃOS JURAMENTADOS',
    r'^O sacrifício', r'^O prêmio do Rei', r'^O Príncipe de Winterfell',
    r'^O prêmio do Rei', r'^O Rei Menino', r'^O Rei na Muralha',
    r'^Rei das Ilhas e do Norte',
]

def is_non_pov(pov: str) -> bool:
    for pat in NON_POV_PATTERNS:
        if re.search(pat, pov):
            return True
    return False


def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Step 1: Revert non-POV chapters back to their original POV-based title
    for book_num in range(1, 6):
        rows = cur.execute("""
            SELECT DISTINCT chapter_number, chapter_title, pov
            FROM paragraphs
            WHERE book_number = ? AND pov IS NOT NULL
            ORDER BY chapter_number
        """, (book_num,)).fetchall()
        for cn, ct, pov in rows:
            if is_non_pov(pov) and ct != pov:
                cur.execute("""
                    UPDATE paragraphs SET chapter_title = ?
                    WHERE book_number = ? AND pov = ? AND chapter_number = ?
                """, (pov, book_num, pov, cn))
                print(f"  [REVERT] Livro {book_num} Cap.{cn}: \"{ct}\" -> \"{pov}\"")

    conn.commit()

    # Step 2: Assign Roman numerals to real POV chapters
    pov_books = [1, 2, 3, 4, 5]
    total_updated = 0

    for book_num in pov_books:
        chapters = cur.execute("""
            SELECT DISTINCT chapter_number, chapter_title, pov
            FROM paragraphs
            WHERE book_number = ? AND pov IS NOT NULL
            ORDER BY chapter_number
        """, (book_num,)).fetchall()

        if not chapters:
            continue

        counts: dict[str, int] = {}
        updates: list[tuple[str, int, str, int, str]] = []

        for cn, ct, pov in chapters:
            if is_non_pov(pov):
                continue

            clean_pov = strip_roman_suffix(pov)
            counts[clean_pov] = counts.get(clean_pov, 0) + 1
            count = counts[clean_pov]
            new_title = f"{clean_pov} {to_roman(count)}"
            updates.append((new_title, book_num, pov, cn, ct))

        for new_title, bn, pv, cn, old_ct in updates:
            cur.execute("""
                UPDATE paragraphs
                SET chapter_title = ?
                WHERE book_number = ? AND pov = ? AND chapter_number = ?
            """, (new_title, bn, pv, cn))

            if new_title != old_ct:
                print(f"  Livro {bn} Cap.{cn:>3}: \"{old_ct}\" -> \"{new_title}\"")

        print(f"  [Livro {book_num}] {len(updates)} capítulos processados")
        total_updated += len(updates)

    conn.commit()
    conn.close()
    print(f"\n[OK] {total_updated} capítulos com POV atualizados.")

if __name__ == "__main__":
    migrate()
