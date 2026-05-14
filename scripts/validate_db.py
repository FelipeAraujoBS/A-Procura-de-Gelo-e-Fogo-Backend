"""
validate_db.py
Valida o banco gerado e exibe estatísticas.
Uso: python validate_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("database.db")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

print("\n=== Estatísticas do banco ===\n")

cur.execute("SELECT COUNT(*) FROM paragraphs")
print(f"Total de parágrafos: {cur.fetchone()[0]:,}")

print("\nPor livro:")
cur.execute("""
    SELECT book_number, book_title, COUNT(*) as total
    FROM paragraphs
    GROUP BY book_number, book_title
    ORDER BY book_number
""")
for row in cur.fetchall():
    print(f"  Livro {row[0]} — {row[1]}: {row[2]:,} parágrafos")

print("\nTop 10 POVs (mais capítulos):")
cur.execute("""
    SELECT pov, COUNT(DISTINCT chapter_number || book_number) as chapters
    FROM paragraphs
    GROUP BY pov
    ORDER BY chapters DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} capítulos")

print("\nTeste de busca — 'dragão':")
cur.execute("""
    SELECT book_title, chapter_title, text
    FROM paragraphs
    WHERE paragraphs MATCH 'dragão'
    LIMIT 3
""")
for row in cur.fetchall():
    print(f"  [{row[0]} / {row[1]}] {row[2][:120]}...")

conn.close()
print("\n[OK] Banco validado com sucesso!")