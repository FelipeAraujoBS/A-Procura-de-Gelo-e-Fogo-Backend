# Uma Busca de Gelo e Fogo — API

**Motor de busca full-text** para *As Crônicas de Gelo e Fogo*. Indexa 10 livros, 2.400+ capítulos e dezenas de milhares de parágrafos de arquivos EPUB, entregando busca por termos, frases exatas e operadores de proximidade com resposta em milissegundos.

> ⚔️ Projetado para performance, escalabilidade zero-copy e experiência de leitura fluida.

---

## Índice

- [Arquitetura](#arquitetura)
- [Pipeline de Dados](#pipeline-de-dados)
- [Motor de Busca](#motor-de-busca)
- [API REST](#api-rest)
- [Segurança](#segurança)
- [Stack Decisões Técnicas](#stack-decisões-técnicas)
- [CI/CD & Deploy](#cicd--deploy)

---

## Arquitetura

```
┌──────────────────────────────────────────────────┐
│                   Cliente                        │
│         (Next.js / cURL / mobile)                │
└──────────────────┬───────────────────────────────┘
                   │ HTTPS
                   ▼
┌──────────────────────────────────────────────────┐
│              Fastify Server (API)                 │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Helmet  │ │  CORS    │ │  Rate Limit       │   │
│  │ (CSP)   │ │ (origins)│ │  (60 req/min)     │   │
│  └─────────┘ └──────────┘ └──────────────────┘   │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Search  │ │  Books   │ │  Chapters / POVs  │   │
│  │ Route   │ │  Route   │ │  Routes           │   │
│  └────┬────┘ └────┬─────┘ └────────┬─────────┘   │
│       │           │                │              │
│       ▼           ▼                ▼              │
│  ┌────────────────────────────────────────────┐   │
│  │         SQLite FTS5 (read-only)            │   │
│  │  paragraphs (FTS5 virtual table)           │   │
│  │  Tokenizer: unicode61                      │   │
│  └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

### Princípios

| Princípio | Aplicação |
|-----------|-----------|
| **Read-only** | Banco aberto em modo `readonly` — zero lock contention |
| **Stateless** | API sem estado de sessão, escala horizontalmente |
| **Defesa em profundidade** | Helmet + CORS + Rate limit em camadas |
| **Zero-copy search** | FTS5 opera direto no índice, sem carregar dados em memória |
| **Fail-fast** | Validação de parâmetros no início de cada request |

---

## Pipeline de Dados

O sistema não é apenas uma API — é uma **plataforma de processamento de livros**:

```
EPUB ──▶ Extração HTML ──▶ Parsing (BeautifulSoup) ──▶ Detecção POV ──▶ FTS5 Index
         │                    │                            │
         ▼                    ▼                            ▼
    toc.ncx              Remove: cover,              Normalização de
    navegação            copyright, toc,             aliases (ex: "Fedor"
                         apêndices, etc.             → "Theon")
```

### Destaques do Parser (`scripts/parse_epubs.py`)

- **Detecção automática de POV**: analisa o primeiro parágrafo de cada documento HTML no EPUB e identifica o personagem narrador por heurística de maiúsculas + lista de POVs conhecidos
- **Resolução de aliases**: mapeia títulos de capítulo ("O Homem do Mercador", "Fedor") para nomes canônicos ("Quentyn Martell", "Theon") via `pov_aliases.json`
- **Theon/Daenerys split**: detecção automática de capítulos de Theon que viram capítulos da Daenerys no meio do texto (ADWD)
- **Numeração romana**: geração automática de títulos como "Bran I", "Catelyn II" baseada na ordenação dos capítulos por POV dentro de cada livro
- **Migração**: script `migrate_chapter_titles.py` para aplicar numeração romana em bancos existentes

### Esquema do Banco

```sql
CREATE VIRTUAL TABLE paragraphs USING fts5(
    book_number,        -- 1 a 10
    book_title,         -- "A Guerra dos Tronos"
    chapter_number,     -- ordinal do capítulo no livro
    chapter_title,      -- "Bran I", "Catelyn II", etc.
    pov,                -- "Bran", "Catelyn" (nome canônico)
    paragraph_index,    -- posição do parágrafo no capítulo
    text,               -- conteúdo textual
    tokenize = 'unicode61'  -- suporte a unicode (português)
);
```

---

## Motor de Busca

### Pipeline da Query

```
Input: "inverno está chegando"
         │
         ▼
   1. Sanitização (escape FTS5 special chars: + ~ ( ) : )
         │
         ▼
   2. Detecção de frase exata (aspas duplas)
         │
         ▼
   3. Para múltiplos termos: operador NEAR(termos, 12)
      (capítulo de distância máxima entre os termos)
         │
         ▼
   4. Execução no índice FTS5 com snippet()
      (6 termos de contexto, <mark> no match)
         │
         ▼
   5. Sanitização do HTML do snippet
         │
         ▼
   6. Paginação (LIMIT/OFFSET, máx 100)
```

### Exemplos de Query

| Input | Comportamento |
|-------|--------------|
| `"Dracarys"` | Frase exata — busca literal |
| `lobos gigantes` | `NEAR(lobos gigantes, 12)` — até 12 palavras de distância |
| `inverno chegando` | `NEAR(inverno chegando, 12)` — ambos os termos próximos |
| `"Valar Morghulis"` | Frase exata — os dois termos juntos |

### Filtros

- **`book`**: filtra por livro específico (WHERE book_number = ?)
- **`povs`**: filtra por múltiplos personagens (WHERE pov IN (...))
- Ambos usam **bind parameters** (não concatenam strings) — sem SQL injection

### Paginação

```json
{
  "total": 142,
  "limit": 20,
  "offset": 0,
  "results": [...]
}
```

Duas queries por requisição: `COUNT(*)` para o total + `SELECT` paginado com `LIMIT/OFFSET`.

---

## API REST

### Endpoints

| Método | Rota | Descrição | Rate Limit |
|--------|------|-----------|------------|
| `GET` | `/health` | Health check (status, timestamp, env) | — |
| `GET` | `/search?q=&book=&povs=&limit=&offset=` | Busca full-text | 30 req/min |
| `GET` | `/books` | Lista livros com contagens | 60 req/min |
| `GET` | `/books/:id` | Detalhe de um livro | 60 req/min |
| `GET` | `/books/:id/chapters` | Capítulos de um livro | 60 req/min |
| `GET` | `/books/:id/chapters/:chapter` | Conteúdo de um capítulo | 60 req/min |
| `GET` | `/context?book=&chapter=&index=` | Parágrafos vizinhos (±3) | 60 req/min |
| `GET` | `/povs?book=` | Personagens POV disponíveis | 60 req/min |

### Resposta de Exemplo

```json
GET /search?q=Dracarys&book=3

{
  "query": "Dracarys",
  "total": 5,
  "limit": 20,
  "offset": 0,
  "results": [
    {
      "book_number": 3,
      "book_title": "A Tormenta de Espadas",
      "chapter_number": 8,
      "chapter_title": "Daenerys I",
      "pov": "Daenerys",
      "paragraph_index": 42,
      "snippet": "...Drogon cuspiu fogo e gritou <mark>Dracarys</mark> enquanto as chamas..."
    }
  ]
}
```

---

## Segurança

| Camada | Implementação |
|--------|--------------|
| **Content Security Policy** | Helmet com diretivas restritivas (default-src 'self') |
| **CORS** | Whitelist de origens via `ALLOWED_ORIGINS`, apenas GET |
| **Rate Limiting** | 60 req/min global, 30 req/min para /search |
| **Input sanitization** | `sanitize-html` nos snippets retornados |
| **SQL Injection** | Todos os parâmetros via bind (prepared statements) |
| **Query sanitization** | Escape de caracteres especiais do FTS5 |

---

## Stack & Decisões Técnicas

### Por que Fastify?

- **Performance**: 2x-3x mais rápido que Express em benchmarks
- **Schema-based**: validação de parâmetros com JSON Schema
- **Plugin system**: modular por rota, fácil de testar
- **Logger nativo**: Pino (JSON estruturado em produção)

### Por que SQLite FTS5?

- **Zero operação**: sem servidor de banco, sem Docker dependente
- **Full-text nativo**: FTS5 é o mecanismo de busca textual mais maduro do SQLite
- **Snippets**: função `snippet()` nativa com destaque de termos
- **Portabilidade**: o banco é um único arquivo — versionável, copiável, deployável
- **Read-only**: sem locks, sem concorrência, sem chance de corrupção em produção

### Decisões de Arquitetura

| Decisão | Alternativa | Por que escolhemos |
|---------|-------------|-------------------|
| Banco único | Elasticsearch / Meilisearch | Dados cabem em 50MB. Um servidor de busca é overkill. |
| Read-only | Read-write | API é consulta pura. Read-only elimina locks e corrupção. |
| Paginação offset | Cursor / search_after | Dataset pequeno (< 100k linhas), offset é simples e suficiente. |
| rate-limit por rota | rate-limit global | `/search` é mais intensivo (FTS5), merece limite mais baixo. |

### Tratamento de Erros

```json
{
  "error": "Parâmetro \"q\" deve ter ao menos 2 caracteres.",
  "statusCode": 400
}
```

- Erros de validação: 400
- Rate limit excedido: 429 com mensagem em português
- Erros internos: 500 (logados no Pino)

---

## CI/CD & Deploy

### GitHub Actions

```yaml
- Cria banco de teste com dados sintéticos
- Roda 29 testes (vitest)
- Build TypeScript
- Separação estrita: CI não precisa de banco real
```

### Deploy (Render)

1. Push na `main` → CI roda testes
2. Render detecta mudança, builda a Docker image
3. Banco `database.db` versionado no repositório (não gitignorado)
4. Volume persistente para o banco em produção

### Docker Compose (dev + prod)

```yaml
services:
  backend:
    build: ./A-Procura-de-Gelo-e-Fogo-Backend
    ports: ["5000:5000"]
    volumes: ["./A-Procura-de-Gelo-e-Fogo-Backend/database.db:/app/database.db"]
```

---

## Variáveis de Ambiente

| Variável | Obrigatório | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `PORT` | Não | 3000 | Porta do servidor |
| `ALLOWED_ORIGINS` | Sim (produção) | — | Origens permitidas no CORS (separadas por vírgula) |
| `NODE_ENV` | Não | development | `production` ativa logs JSON estruturados |
| `DB_PATH` | Não | ./database.db | Caminho do banco SQLite |

---

## Testes

```bash
npm test           # 29 testes
npm run test:watch # Modo watch
```

Os testes usam `vitest` + `supertest` e criam um banco isolado com dados sintéticos. Validam:

- Busca por termo único e múltiplo
- Busca por frase exata
- Filtros por livro e POV
- Paginação
- Rate limiting
- Health check
- Validação de parâmetros

---

> Projetado e desenvolvido por [FelipeAraujoBS](https://github.com/FelipeAraujoBS)
