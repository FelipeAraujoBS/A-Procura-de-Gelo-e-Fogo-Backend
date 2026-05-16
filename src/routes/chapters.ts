import { FastifyInstance } from 'fastify'
import db from '../db.js'
import { Chapter } from '../types/index.js'

export default async function chaptersRoute(app: FastifyInstance) {
  app.get<{ Params: { id: string } }>('/books/:id/chapters', async (req, reply) => {
    const bookId = Number(req.params.id)

    const chapters = db.prepare(`
      SELECT
        chapter_number,
        chapter_title,
        pov,
        COUNT(*) AS paragraph_count
      FROM paragraphs
      WHERE book_number = ?
      GROUP BY chapter_number, chapter_title, pov
      ORDER BY chapter_number
    `).all(bookId)

    if (!chapters.length) return reply.status(404).send({ error: 'Livro não encontrado.' })
    return { book_number: bookId, chapters: chapters as Chapter[] }
  })

  app.get<{ Params: { id: string; chapter: string } }>(
    '/books/:id/chapters/:chapter',
    async (req, reply) => {
      const rows = db.prepare(`
        SELECT
          book_number, book_title,
          chapter_number, chapter_title, pov,
          paragraph_index, text
        FROM paragraphs
        WHERE book_number = ? AND chapter_number = ?
        ORDER BY paragraph_index
      `).all(Number(req.params.id), Number(req.params.chapter))

      if (!rows.length) return reply.status(404).send({ error: 'Capítulo não encontrado.' })
      return {
        book_number:    Number(req.params.id),
        chapter_number: Number(req.params.chapter),
        chapter_title:  (rows[0] as any).chapter_title,
        pov:            (rows[0] as any).pov,
        paragraphs:     rows,
      }
    }
  )

  app.get<{ Querystring: { book: string; chapter: string; index: string } }>(
    '/context',
    async (req, reply) => {
      const { book, chapter, index } = req.query
      const idx = Number(index)

      if (!book || !chapter || isNaN(idx)) {
        return reply.status(400).send({ error: 'Parâmetros inválidos.' })
      }

      const paragraphs = db.prepare(`
        SELECT paragraph_index, text
        FROM paragraphs
        WHERE book_number = ? AND chapter_number = ?
          AND paragraph_index BETWEEN ? AND ?
        ORDER BY paragraph_index
      `).all(Number(book), Number(chapter), Math.max(0, idx - 3), idx + 3)

      return { paragraphs }
    }
  )
}