import { describe, it, expect, afterAll, beforeAll } from 'vitest'
import supertest from 'supertest'
import { FastifyInstance } from 'fastify'
import { buildApp, registerPlugins } from '../src/server.js'

describe('GET /books/:id/chapters', () => {
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

  it('retorna capítulos do livro', async () => {
    const res = await request.get('/books/1/chapters')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('book_number')
    expect(res.body).toHaveProperty('chapters')
    expect(Array.isArray(res.body.chapters)).toBe(true)
  })

  it('retorna 404 para livro inexistente', async () => {
    const res = await request.get('/books/9999/chapters')
    expect(res.status).toBe(404)
    expect(res.body).toHaveProperty('error')
  })
})

describe('GET /books/:id/chapters/:chapter', () => {
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

  it('retorna capítulo específico com parágrafos', async () => {
    const res = await request.get('/books/1/chapters/1')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('book_number')
    expect(res.body).toHaveProperty('chapter_number')
    expect(res.body).toHaveProperty('chapter_title')
    expect(res.body).toHaveProperty('pov')
    expect(res.body).toHaveProperty('paragraphs')
    expect(Array.isArray(res.body.paragraphs)).toBe(true)
  })

  it('retorna 404 para capítulo inexistente', async () => {
    const res = await request.get('/books/1/chapters/9999')
    expect(res.status).toBe(404)
    expect(res.body).toHaveProperty('error')
  })
})

describe('GET /context', () => {
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

  it('retorna contexto ao redor de um parágrafo', async () => {
    const res = await request.get('/context?book=1&chapter=1&index=5')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('paragraphs')
    expect(Array.isArray(res.body.paragraphs)).toBe(true)
  })

  it('retorna 400 para parâmetros inválidos', async () => {
    const res = await request.get('/context?book=1&chapter=1&index=abc')
    expect(res.status).toBe(400)
    expect(res.body).toHaveProperty('error')
  })

  it('retorna 400 para parâmetros ausentes', async () => {
    const res = await request.get('/context?book=1')
    expect(res.status).toBe(400)
  })
})