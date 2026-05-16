import { FastifyInstance } from 'fastify'
import db from '../db.js'
import { SearchResponse } from '../types/index.js'
import { sanitizeSnippet } from '../utils/sanitize.js'

interface SearchQuery {
  q: string
  book?: string
  povs?: string
  limit?: string
  offset?: string
}

export default async function searchRoute(app: FastifyInstance) {
  app.get<{ Querystring: SearchQuery }>('/search', {
    config: {
      rateLimit: {
        max: 30,
        timeWindow: '1 minute'
      }
    }
  }, async (req, reply) => {
    const { q, book, povs, limit = '20', offset = '0' } = req.query

    if (!q || q.trim().length < 2) {
      return reply.status(400).send({ error: 'Parâmetro "q" deve ter ao menos 2 caracteres.' })
    }

    const limitNum  = Math.min(Math.max(Number(limit)  || 20, 1), 100)
    const offsetNum = Math.max(Number(offset) || 0, 0)

    let sql = `
      SELECT
        book_number,
        book_title,
        chapter_number,
        chapter_title,
        pov,
        paragraph_index,
        snippet(paragraphs, 6, '<mark>', '</mark>', '...', 24) AS snippet
      FROM paragraphs
      WHERE paragraphs MATCH ?
    `
    const params: unknown[] = [q.trim()]

    if (book) {
      sql += ` AND book_number = ?`
      params.push(Number(book))
    }

    if (povs) {
      const povList = povs.split(',').map(p => p.trim()).filter(p => p)
      if (povList.length > 0) {
        const placeholders = povList.map(() => '?').join(',')
        sql += ` AND pov IN (${placeholders})`
        params.push(...povList)
      }
    }

    sql += ` ORDER BY book_number ASC, chapter_number ASC, paragraph_index ASC LIMIT ? OFFSET ?`
    params.push(limitNum, offsetNum)

    let countSql = `SELECT COUNT(*) as total FROM paragraphs WHERE paragraphs MATCH ?`
    const countParams: unknown[] = [q.trim()]
    if (book) { countSql += ` AND book_number = ?`; countParams.push(Number(book)) }
    if (povs) {
      const povList = povs.split(',').map(p => p.trim()).filter(p => p)
      if (povList.length > 0) {
        const placeholders = povList.map(() => '?').join(',')
        countSql += ` AND pov IN (${placeholders})`
        countParams.push(...povList)
      }
    }

    const { total } = db.prepare(countSql).get(...countParams) as { total: number }
    const results   = db.prepare(sql).all(...params) as any[]

    const sanitizedResults = results.map((r) => ({
      ...r,
      snippet: sanitizeSnippet(r.snippet),
    }))

    const response: SearchResponse = {
      query:   q.trim(),
      total,
      limit:   limitNum,
      offset:  offsetNum,
      results: sanitizedResults,
    }

    return response
  })
}