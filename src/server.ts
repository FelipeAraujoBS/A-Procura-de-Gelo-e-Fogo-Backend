import 'dotenv/config'
import Fastify from 'fastify'
import cors from '@fastify/cors'
import helmet from '@fastify/helmet'
import rateLimit from '@fastify/rate-limit'
import pino from 'pino'
import { Transform } from 'stream'
import { hostname } from 'os'

import searchRoute   from './routes/search.js'
import booksRoute    from './routes/books.js'
import chaptersRoute from './routes/chapters.js'
import povsRoute     from './routes/povs.js'
import chatRoute     from './routes/chat.js'

const isProd = process.env.NODE_ENV === 'production'
const port   = Number(process.env.PORT) || 3000

const allowedOrigins = (process.env.ALLOWED_ORIGINS ?? 'http://localhost:3000')
  .split(',')
  .map(o => o.trim())
  .filter(Boolean)

if (isProd && allowedOrigins.length === 0) {
  console.error('ERRO: ALLOWED_ORIGINS não configurado em produção.')
  process.exit(1)
}

function buildLogger() {
  const INGESTOR_URL = process.env.LOGFLOW_URL ?? 'http://localhost:3000'
  const API_KEY = process.env.LOGFLOW_API_KEY
  const streams: pino.StreamEntry[] = []

  if (isProd) {
    streams.push({ stream: pino.destination(1) })
  } else {
    streams.push({
      stream: pino.transport({
        target: 'pino-pretty',
        options: { colorize: true },
      }),
    })
  }

  if (API_KEY) {
    streams.push({
      stream: new Transform({
        objectMode: true,
        transform(chunk: any, _enc: any, callback: any) {
          fetch(`${INGESTOR_URL}/api/v1/logs`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${API_KEY}`,
            },
            body: JSON.stringify({
              severity:
                chunk.level >= 50 ? 'FATAL'
                : chunk.level >= 40 ? 'ERROR'
                : chunk.level >= 30 ? 'WARN'
                : chunk.level >= 20 ? 'INFO'
                : 'DEBUG',
              service: {
                name: chunk.name ?? 'gelo-fogo-api',
                version: process.env.APP_VERSION ?? '1.0.0',
                environment: isProd ? 'production' : 'development',
                host: chunk.hostname ?? hostname(),
              },
              message: chunk.msg,
              timestamp: chunk.time ? new Date(chunk.time).toISOString() : new Date().toISOString(),
              metadata: {
                reqId: chunk.reqId,
                ...(chunk.err ? { error: chunk.err } : {}),
              },
            }),
          }).catch(() => {})
          callback(null, chunk)
        },
      }),
    })
  }

  return pino(
    { level: isProd ? 'info' : 'debug' },
    pino.multistream(streams),
  )
}

export function buildApp(opts = {}) {
  return Fastify({
    logger: buildLogger(),
    ...opts,
  })
}

export async function registerPlugins(app: ReturnType<typeof buildApp>) {
  await app.register(helmet, {
    contentSecurityPolicy: {
      directives: {
        defaultSrc:  ["'self'"],
        scriptSrc:   ["'self'"],
        styleSrc:    ["'self'", "'unsafe-inline'"],
        imgSrc:      ["'self'", 'data:'],
        connectSrc:  ["'self'", ...allowedOrigins],
      },
    },
  })

  await app.register(cors, {
    origin: (origin, cb) => {
      if (!origin) {
        cb(null, true)
        return
      }
      if (allowedOrigins.includes(origin)) {
        cb(null, true)
      } else {
        cb(new Error(`Origem não permitida pelo CORS: ${origin}`), false)
      }
    },
    methods: ['GET', 'POST'],
    allowedHeaders: ['Content-Type'],
    maxAge: 86400,
  })

  await app.register(rateLimit, {
    global: true,
    max: 60,
    timeWindow: '1 minute',
    errorResponseBuilder: (_req, context) => ({
      error: 'Too Many Requests',
      message: `Limite de requisições atingido. Tente novamente em ${context.after}.`,
      statusCode: 429,
    }),
  })

  await app.register(searchRoute)
  await app.register(booksRoute)
  await app.register(chaptersRoute)
  await app.register(povsRoute)
  await app.register(chatRoute)

  app.get('/health', async () => ({
    status: 'ok',
    timestamp: new Date().toISOString(),
    env: process.env.NODE_ENV,
  }))

  app.setErrorHandler((error, req, reply) => {
    const err = error as Error
    if (reply.statusCode !== 429) {
      app.log.error({ err: error, url: req.url }, 'Erro na requisição')
    }
    reply.status(reply.statusCode || 500).send({
      error: err?.message || 'Erro interno do servidor.',
    })
  })
}

const app = buildApp()

async function start() {
  await registerPlugins(app)

  try {
    await app.listen({ port, host: '0.0.0.0' })
    console.log(`API rodando em http://localhost:${port}`)
  } catch (err) {
    app.log.error(err)
    process.exit(1)
  }
}

if (process.argv[1]?.endsWith('server.ts') || process.argv[1]?.endsWith('server.js')) {
  start()
}

export { start }