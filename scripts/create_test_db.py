"""
create_test_db.py
Cria um database.db mínimo com dados de teste para CI/CD.
Uso: python scripts/create_test_db.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")

def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
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

    test_rows = [
        (1, "A Guerra dos Tronos", 1, "Bran I", "Bran", 0, "Bran observou os lobos gigantes correndo pela neve."),
        (1, "A Guerra dos Tronos", 1, "Bran I", "Bran", 1, "Os lobos brancos eram magníficos naquela manhã fria."),
        (1, "A Guerra dos Tronos", 2, "Catelyn I", "Catelyn", 0, "Catelyn sabia que o inverno estava chegando."),
        (1, "A Guerra dos Tronos", 3, "Jon I", "Jon", 0, "Jon Snow olhou para o Norte e pensou em seu futuro."),
        (1, "A Guerra dos Tronos", 3, "Jon I", "Jon", 1, "Você não sabe de nada, Jon Snow, disse Ygritte."),
        (1, "A Guerra dos Tronos", 4, "Daenerys I", "Daenerys", 0, "Daenerys Targaryen sonhava com dragões e fogo."),
        (1, "A Guerra dos Tronos", 4, "Daenerys I", "Daenerys", 1, "Dracarys, ela sussurrou e o dragão obedeceu."),
        (1, "A Guerra dos Tronos", 5, "Tyrion I", "Tyrion", 0, "Um Lannister sempre paga suas dívidas, Tyrion sorriu."),
        (1, "A Guerra dos Tronos", 5, "Tyrion I", "Tyrion", 1, "Quando você joga o jogo dos tronos, você vence ou morre."),
        (1, "A Guerra dos Tronos", 6, "Eddard I", "Eddard", 0, "Eddard Stark era o senhor de Winterfell e guardião do Norte."),
        (2, "A Fúria dos Reis", 1, "Arya I", "Arya", 0, "Arya Stark praticava esgrima com sua espada Agulha."),
        (2, "A Fúria dos Reis", 2, "Sansa I", "Sansa", 0, "Sansa olhou para o trono de ferro com medo e admiração."),
        (2, "A Fúria dos Reis", 3, "Jon I", "Jon", 0, "Jon Snow jurou proteger a Muralha contra os selvagens."),
        (3, "A Tormenta de Espadas", 1, "Jaime I", "Jaime", 0, "Jaime Lannister perdeu sua mão de espada."),
        (3, "A Tormenta de Espadas", 2, "Arya I", "Arya", 0, "Valar Morghulis, disse Arya ao homem sem rosto."),
        (4, "Um Festim para Corvos", 1, "Cersei I", "Cersei", 0, "Cersei Lannister governava Porto Real com mão de ferro."),
        (4, "Um Festim para Corvos", 2, "Brienne I", "Brienne", 0, "Brienne de Tarth buscava Sansa Stark para protegê-la."),
        (5, "A Dança dos Dragões", 1, "Jon I", "Jon", 0, "Jon Snow foi eleito Lord Comandante da Patrulha da Noite."),
        (5, "A Dança dos Dragões", 2, "Daenerys I", "Daenerys", 0, "Daenerys governava Meereen com justiça e compaixão."),
        (5, "A Dança dos Dragões", 3, "Tyrion I", "Tyrion", 0, "Tyrion viajou por Essia em busca de um novo propósito."),
    ]

    cur.executemany("""
        INSERT INTO paragraphs (
            book_number, book_title, chapter_number,
            chapter_title, pov, paragraph_index, text
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, test_rows)

    conn.commit()
    conn.close()

    print(f"[OK] Banco de teste criado em {DB_PATH}")
    print(f"   {len(test_rows)} parágrafos inseridos")

if __name__ == "__main__":
    main()
