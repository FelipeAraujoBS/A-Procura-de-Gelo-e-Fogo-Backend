import { FastifyInstance } from 'fastify'
import db from '../db.js'
import { Pov } from '../types/index.js'

const EXCLUDED_POV_PATTERNS = [
  'O Rei ', 'O REI ', 'Rei das Ilhas', 'REI DAS ILHAS',
  'Prólogo', 'Epílogo', 'Desconhecido',
  'Uma observação sobre a cronologia',
  'Para lá da muralha', 'Na antiga Volantis', 'Na Baía dos Escravos',
  'Em Bravos', 'EM BRAVOS', 'ENQUANTO ISSO',
  'SENHORES MENORES', 'FORAS DA LEI', 'IRMÃOS JURAMENTADOS',
  'O sacrifício', 'O prêmio do Rei', 'O Príncipe de Winterfell',
  'Catelyn ', 'Arya ', 'Tyrion ', 'Jon ', 'Samwell ',
]

export default async function povsRoute(app: FastifyInstance) {
  app.get('/povs', async (req) => {
    const { book } = req.query as { book?: string }

    const excludeConditions = EXCLUDED_POV_PATTERNS.map(() =>
      `pov NOT LIKE ?`
    ).join(' AND ')

    const params: unknown[] = [
      ...EXCLUDED_POV_PATTERNS.map(p => `%${p}%`),
    ]

    let sql = `
      SELECT
        pov,
        COUNT(DISTINCT book_number || '-' || chapter_number) AS chapter_count,
        COUNT(DISTINCT book_number)                          AS book_count
      FROM paragraphs
      WHERE pov IS NOT NULL
    `
    sql += ` AND (${excludeConditions})`

    if (book) {
      sql += ` AND book_number = ?`
      params.push(Number(book))
    }

    sql += ` GROUP BY pov ORDER BY chapter_count DESC`

    const povs = db.prepare(sql).all(...params)
    return { povs: povs as Pov[] }
  })
}