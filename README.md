# Search Backend

API de busca full-text para os livros de "As Crônicas de Gelo e Fogo" (Game of Thrones).

## Tech Stack

- **Fastify** - Framework web
- **SQLite + FTS5** - Banco de dados com busca full-text
- **TypeScript** - Linguagem

## Instalação

```bash
npm install
```

## Executar

```bash
# Desenvolvimento
npm run dev

# Produção
npm run build
npm run start
```

A API estará disponível em `http://localhost:5000`

## Endpoints

### Health Check
```
GET /health
```

### Busca
```
GET /search?q=<termo>&book=<id>&pov=<personagem>&limit=20&offset=0
```

Busca full-text nos parágrafos dos livros. Retorna snippets com highlight.

Parâmetros:
- `q` (obrigatório) - Termo de busca (mínimo 2 caracteres)
- `book` (opcional) - Filtrar por número do livro
- `pov` (opcional) - Filtrar por ponto de vista
- `limit` (opcional, padrão: 20) - Limite de resultados
- `offset` (opcional, padrão: 0) - Offset para paginação

### Livros
```
GET /books
GET /books/:id
```

Lista todos os livros ou obtém um livro específico.

### Capítulos
```
GET /books/:id/chapters
GET /books/:id/chapters/:chapter
```

Lista capítulos de um livro ou obtém o conteúdo de um capítulo específico.

### POVs (Personagens)
```
GET /povs?book=<id>
```

Lista personagens que servem como ponto de vista narrativo, com contagem de capítulos e livros.

## Scripts

- `scripts/parse_epubs.py` - Parser de EPUBs para extrair texto e criar o banco de dados
- `scripts/validate_db.py` - Valida a estrutura do banco de dados

## Banco de Dados

O projeto utiliza SQLite com FTS5 para busca full-text. O arquivo `database.db` deve estar na raiz do projeto.