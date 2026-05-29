import { FastifyInstance } from 'fastify'
import db from '../db.js'

interface ChatBody {
  messages: { role: string; content: string }[]
}

function escapeFts5SpecialChars(query: string): string {
  return query
    .replace(/"/g, '""')
    .replace(/\+/g, '')
    .replace(/~/g, '')
    .replace(/\(/g, '')
    .replace(/\)/g, '')
    .replace(/:/g, '')
    .replace(/\bAND\b/gi, '')
    .replace(/\bOR\b/gi, '')
    .replace(/\bNOT\b/gi, '')
}

function buildFts5Query(raw: string): string {
  const trimmed = raw.trim()
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    const inner = trimmed.slice(1, -1)
    return `"${escapeFts5SpecialChars(inner)}"`
  }
  const terms = trimmed
    .replace(/[.,;:!?()]/g, ' ')
    .split(/\s+/)
    .map(t => t.trim())
    .filter(t => t.length > 0)
  if (terms.length <= 1) return escapeFts5SpecialChars(trimmed)
  const escaped = terms.map(t => escapeFts5SpecialChars(t))
  return `NEAR(${escaped.join(' ')}, 12)`
}

function buildReply(sources: { book_title: string; chapter_title: string; chapter_number: number; text: string }[]): string {
  if (sources.length === 0) {
    return 'Nada encontrado nos pergaminhos. Tente perguntar de outra forma.'
  }

  const books = [...new Set(sources.map(s => s.book_title))]
  const bookList = books.length === 1
    ? books[0]
    : books.slice(0, -1).join(', ') + ' e ' + books[books.length - 1]

  return `Encontrei ${sources.length} passagem(ns) relevante(s) em ${bookList}:`
}

export default async function chatRoute(app: FastifyInstance) {
  app.post<{ Body: ChatBody }>('/api/chat', async (req, reply) => {
    const { messages } = req.body

    if (!messages || messages.length === 0) {
      return reply.status(400).send({ error: 'Nenhuma mensagem enviada.' })
    }

    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUserMsg || !lastUserMsg.content.trim()) {
      return reply.status(400).send({ error: 'Nenhuma pergunta do usuário encontrada.' })
    }

    const query = lastUserMsg.content.trim()
    if (query.length < 2) {
      return reply.status(400).send({ error: 'A pergunta deve ter ao menos 2 caracteres.' })
    }

    try {
      const ftsQuery = buildFts5Query(query)

      const sql = `
        SELECT
          book_number,
          book_title,
          chapter_number,
          chapter_title,
          paragraph_index,
          text
        FROM paragraphs
        WHERE paragraphs MATCH ?
        ORDER BY rank
        LIMIT 5
      `
      const results = db.prepare(sql).all(ftsQuery) as any[]

      const sources = results.map(r => ({
        book_title:   r.book_title,
        chapter_title: r.chapter_title,
        chapter_number: r.chapter_number,
        text:          r.text.slice(0, 300),
      }))

      const replyContent = buildReply(sources)

      return {
        reply: {
          id: `chat_${Date.now()}`,
          role: 'assistant',
          content: replyContent,
          sources: sources.length > 0 ? sources : undefined,
          timestamp: Date.now(),
        },
      }
    } catch (error) {
      app.log.error(error)
      return reply.status(500).send({
        reply: {
          id: `chat_${Date.now()}`,
          role: 'assistant',
          content: 'Perdoe-me, não consegui consultar os pergaminhos agora.',
          timestamp: Date.now(),
        },
      })
    }
  })
}
