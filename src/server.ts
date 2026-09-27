import 'dotenv/config'
import Fastify, { FastifyInstance } from 'fastify'
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
      level: isProd ? 'info' : 'debug',
      stream: new Transform({
        // pino.multistream entrega string/Buffer JSON, não objeto.
        transform(chunk: any, _enc: any, callback: any) {
          let log: any
          try {
            const raw = typeof chunk === 'string' ? chunk : chunk.toString('utf8')
            log = JSON.parse(raw)
          } catch {
            callback()
            return
          }
          fetch(`${INGESTOR_URL}/api/v1/logs`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${API_KEY}`,
            },
            body: JSON.stringify({
              severity:
                log.level >= 50 ? 'FATAL'
                : log.level >= 40 ? 'ERROR'
                : log.level >= 30 ? 'WARN'
                : log.level >= 20 ? 'INFO'
                : 'DEBUG',
              service: {
                name: log.name ?? 'gelo-fogo-api',
                version: process.env.APP_VERSION ?? '1.0.0',
                environment: isProd ? 'production' : 'development',
                host: log.hostname ?? hostname(),
              },
              message: log.msg,
              timestamp: log.time ? new Date(log.time).toISOString() : new Date().toISOString(),
              metadata: {
                reqId: log.reqId,
                ...(log.err ? { error: log.err } : {}),
              },
            }),
          }).catch(() => {})
          callback()
        },
      }),
    })
  }

  return pino(
    { level: isProd ? 'info' : 'debug' },
    pino.multistream(streams),
  )
}

export function buildApp(opts: Record<string, any> = {}): FastifyInstance {
  // Fastify v5: `logger` aceita apenas objeto de config; instância pino vai em `loggerInstance`.
  if (opts.logger === undefined && opts.loggerInstance === undefined) {
    return Fastify({
      loggerInstance: buildLogger(),
      ...opts,
    }) as unknown as FastifyInstance
  }
  return Fastify(opts) as unknown as FastifyInstance
}

export async function registerPlugins(app: FastifyInstance) {
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
    origin: async (origin: string | undefined): Promise<boolean> => {
      if (!origin || allowedOrigins.includes(origin)) {
        return true
      }
      throw new Error(`Origem não permitida pelo CORS: ${origin}`)
    },
    methods: ['GET', 'POST'],
    allowedHeaders: ['Content-Type'],
    maxAge: 86400,
  })

  await app.register(rateLimit, {
    global: true,
    max: 60,
    timeWindow: '1 minute',
    errorResponseBuilder: (_req: any, context: { after: string }) => ({
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