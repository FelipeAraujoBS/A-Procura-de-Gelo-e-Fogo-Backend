import { FastifyInstance } from 'fastify'
import db from '../db.js'
import { Book } from '../types/index.js'

export default async function booksRoute(app: FastifyInstance) {
  app.get('/books', async () => {
    const books = db.prepare(`
      SELECT
        book_number,
        book_title,
        COUNT(DISTINCT chapter_number) AS chapter_count,
        COUNT(*)                       AS paragraph_count
      FROM paragraphs
      GROUP BY book_number, book_title
      ORDER BY book_number
    `).all()

    return { books: books as Book[] }
  })

  app.get<{ Params: { id: string } }>('/books/:id', async (req, reply) => {
    const book = db.prepare(`
      SELECT
        book_number,
        book_title,
        COUNT(DISTINCT chapter_number) AS chapter_count,
        COUNT(*)                       AS paragraph_count
      FROM paragraphs
      WHERE book_number = ?
      GROUP BY book_number, book_title
    `).get(Number(req.params.id))

    if (!book) return reply.status(404).send({ error: 'Livro não encontrado.' })
    return book
  })
}