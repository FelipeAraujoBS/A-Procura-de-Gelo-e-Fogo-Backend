#!/bin/sh
set -e

if [ ! -f /app/database.db ]; then
  echo "ERRO: database.db não encontrado. Gere o banco localmente com 'npm run seed' antes do build."
  exit 1
fi

echo "Database verificado. Iniciando API..."
exec "$@"
