import { FastifyInstance } from 'fastify'
import db from '../db.js'
import { Pov } from '../types/index.js'

export default async function povsRoute(app: FastifyInstance) {
  app.get('/povs', async (req) => {
    const { book } = req.query as { book?: string }

    let sql = `
      SELECT
        pov,
        COUNT(DISTINCT book_number || '-' || chapter_number) AS chapter_count,
        COUNT(DISTINCT book_number)                          AS book_count
      FROM paragraphs
    `
    const params: unknown[] = []

    if (book) {
      sql += ` WHERE book_number = ?`
      params.push(Number(book))
    }

    sql += ` GROUP BY pov ORDER BY chapter_count DESC`

    const povs = db.prepare(sql).all(...params)
    return { povs: povs as Pov[] }
  })
}