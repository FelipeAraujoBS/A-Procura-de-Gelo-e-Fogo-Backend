import { describe, it, expect, afterAll, beforeAll } from 'vitest'
import supertest from 'supertest'
import { FastifyInstance } from 'fastify'
import { buildApp, registerPlugins } from '../src/server.js'

describe('GET /books', () => {
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

  it('retorna lista de livros', async () => {
    const res = await request.get('/books')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('books')
    expect(Array.isArray(res.body.books)).toBe(true)
  })

  it('retorna livro com propriedades corretas', async () => {
    const res = await request.get('/books')
    expect(res.status).toBe(200)
    if (res.body.books.length > 0) {
      const book = res.body.books[0]
      expect(book).toHaveProperty('book_number')
      expect(book).toHaveProperty('book_title')
      expect(book).toHaveProperty('chapter_count')
      expect(book).toHaveProperty('paragraph_count')
    }
  })
})

describe('GET /books/:id', () => {
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

  it('retorna livro específico por ID', async () => {
    const res = await request.get('/books/1')
    expect(res.status).toBe(200)
    expect(res.body.book_number).toBe(1)
  })

  it('retorna 404 para livro inexistente', async () => {
    const res = await request.get('/books/9999')
    expect(res.status).toBe(404)
    expect(res.body).toHaveProperty('error')
  })
})