import { describe, it, expect, afterAll, beforeAll } from 'vitest'
import supertest from 'supertest'
import { FastifyInstance } from 'fastify'
import { buildApp, registerPlugins } from '../src/server.js'

describe('GET /povs', () => {
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

  it('retorna lista de povs', async () => {
    const res = await request.get('/povs')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('povs')
    expect(Array.isArray(res.body.povs)).toBe(true)
  })

  it('retorna povs ordenados por capítulo (mais relevante primeiro)', async () => {
    const res = await request.get('/povs')
    expect(res.status).toBe(200)
    if (res.body.povs.length >= 2) {
      expect(res.body.povs[0].chapter_count).toBeGreaterThanOrEqual(res.body.povs[1].chapter_count)
    }
  })

  it('retorna pov com propriedades corretas', async () => {
    const res = await request.get('/povs')
    expect(res.status).toBe(200)
    if (res.body.povs.length > 0) {
      const pov = res.body.povs[0]
      expect(pov).toHaveProperty('pov')
      expect(pov).toHaveProperty('chapter_count')
      expect(pov).toHaveProperty('book_count')
    }
  })

  it('filtra por livro com parâmetro "book"', async () => {
    const res = await request.get('/povs?book=1')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('povs')
  })
})

describe('GET /health', () => {
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

  it('retorna status ok', async () => {
    const res = await request.get('/health')
    expect(res.status).toBe(200)
    expect(res.body.status).toBe('ok')
  })

  it('retorna timestamp', async () => {
    const res = await request.get('/health')
    expect(res.body).toHaveProperty('timestamp')
    expect(new Date(res.body.timestamp).toString()).not.toBe('Invalid Date')
  })
})