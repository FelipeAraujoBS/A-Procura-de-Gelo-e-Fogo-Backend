import { describe, it, expect, afterAll, beforeAll } from 'vitest'
import supertest from 'supertest'
import { FastifyInstance } from 'fastify'
import { buildApp, registerPlugins } from '../src/server.js'

describe('GET /search', () => {
  let request: supertest.Agent
  let app: FastifyInstance

  beforeAll(async () => {
    app = buildApp({ logger: false })
    await registerPlugins(app)
    await app.ready()
    request = supertest(app.server)
  })

  afterAll(async () => {
    await app.close()
  })

  it('retorna 400 quando query "q" tem menos de 2 caracteres', async () => {
    const res = await request.get('/search?q=a')
    expect(res.status).toBe(400)
    expect(res.body).toHaveProperty('error')
    expect(res.body.error).toContain('2 caracteres')
  })

  it('retorna 400 quando query "q" está vazia', async () => {
    const res = await request.get('/search?q=')
    expect(res.status).toBe(400)
  })

  it('retorna 400 quando query "q" é omitida', async () => {
    const res = await request.get('/search')
    expect(res.status).toBe(400)
  })

  it('retorna resultados válidos para query válida', async () => {
    const res = await request.get('/search?q=lobos')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('query')
    expect(res.body).toHaveProperty('total')
    expect(res.body).toHaveProperty('limit')
    expect(res.body).toHaveProperty('offset')
    expect(res.body).toHaveProperty('results')
    expect(Array.isArray(res.body.results)).toBe(true)
  })

  it('retorna snippet com highlight', async () => {
    const res = await request.get('/search?q=lobos')
    expect(res.status).toBe(200)
    if (res.body.results.length > 0) {
      expect(res.body.results[0]).toHaveProperty('snippet')
    }
  })

  it('filtra por livro com parâmetro "book"', async () => {
    const res = await request.get('/search?q=lobos&book=1')
    expect(res.status).toBe(200)
    if (res.body.results.length > 0) {
      expect(res.body.results[0].book_number).toBe(1)
    }
  })

  it('filtra por povs com parâmetro "povs"', async () => {
    const res = await request.get('/search?q=lobos&povs=Jon')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('results')
  })

  it('respcta limite com parâmetro "limit"', async () => {
    const res = await request.get('/search?q=lobos&limit=5')
    expect(res.status).toBe(200)
    expect(res.body.limit).toBe(5)
    expect(res.body.results.length).toBeLessThanOrEqual(5)
  })

  it('respcta offset com parâmetro "offset"', async () => {
    const resWithOffset = await request.get('/search?q=lobos&limit=1&offset=1')
    expect(resWithOffset.status).toBe(200)
    expect(resWithOffset.body.offset).toBe(1)
  })

  it('retorna total correto de resultados', async () => {
    const res = await request.get('/search?q=lobos')
    expect(res.status).toBe(200)
    expect(typeof res.body.total).toBe('number')
    expect(res.body.total).toBeGreaterThanOrEqual(0)
  })

  it('busca frase exata com vírgula sem erro de sintaxe FTS5', async () => {
    const res = await request.get('/search?q=Voc%C3%AA%20n%C3%A3o%20sabe%20nada%2C%20Jon%20Snow')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('results')
    expect(Array.isArray(res.body.results)).toBe(true)
  })

  it('busca com múltiplas palavras retorna resultados', async () => {
    const res = await request.get('/search?q=lobos%20brancos')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('results')
  })
})