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
- `scripts/create_test_db.py` - Cria banco de dados mínimo para testes/CI

## Banco de Dados

O projeto utiliza SQLite com FTS5 para busca full-text. O arquivo `database.db` deve estar na raiz do projeto.

## Variáveis de Ambiente

Crie um arquivo `.env` baseado no `.env.example`:

```env
PORT=5000
ALLOWED_ORIGINS=http://localhost:3000
NODE_ENV=development
```

Em produção, defina `ALLOWED_ORIGINS` com o domínio real do frontend:

```env
ALLOWED_ORIGINS=https://seudominio.com
NODE_ENV=production
```

## Deploy

### Docker

```bash
docker build -t search-backend .
docker run -p 5000:5000 \
  -e NODE_ENV=production \
  -e ALLOWED_ORIGINS=https://seudominio.com \
  search-backend
```

### Railway

1. Conecte o repositório ao Railway
2. Defina o diretório raiz como `A-Procura-de-Gelo-e-Fogo-Backend`
3. Adicione as variáveis de ambiente:
   - `NODE_ENV=production`
   - `ALLOWED_ORIGINS=https://frontend-url.com`
4. Faça upload do `database.db` via Railway shell ou volume persistente

### Render

1. Crie um novo Web Service apontando para o repositório
2. Build Command: `cd A-Procura-de-Gelo-e-Fogo-Backend && npm install && npm run build`
3. Start Command: `cd A-Procura-de-Gelo-e-Fogo-Backend && npm start`
4. Adicione as variáveis de ambiente necessárias
5. Use um volume persistente para o `database.db`

### VPS com Docker Compose

Veja `docker-compose.yml` na raiz do projeto para subir backend + frontend juntos.
