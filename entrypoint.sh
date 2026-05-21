#!/bin/sh
set -e

if [ ! -f /app/database.db ]; then
  echo "AVISO: database.db nao encontrado. Criando banco minimo..."
  if command -v python3 >/dev/null 2>&1; then
    python3 /app/scripts/create_test_db.py
  elif command -v python >/dev/null 2>&1; then
    python /app/scripts/create_test_db.py
  elif command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 /app/database.db "CREATE VIRTUAL TABLE paragraphs USING fts5(book_number, book_title, chapter_number, chapter_title, pov, paragraph_index, text, tokenize = 'unicode61');"
    echo "Banco minimo criado com sqlite3."
  else
    echo "ERRO: database.db nao encontrado e nenhuma ferramenta disponivel para cria-lo."
    echo "Monte o database.db como volume ou gere com 'npm run seed'."
    exit 1
  fi
fi

echo "Database verificado. Iniciando API..."
exec "$@"
