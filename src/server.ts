import 'dotenv/config'
import Fastify from 'fastify'
import cors from '@fastify/cors'
import helmet from '@fastify/helmet'
import rateLimit from '@fastify/rate-limit'

import searchRoute   from './routes/search.js'
import booksRoute    from './routes/books.js'
import chaptersRoute from './routes/chapters.js'
import povsRoute     from './routes/povs.js'

const isProd = process.env.NODE_ENV === 'production'
const port   = Number(process.env.PORT) || 3000

const allowedOrigins = (process.env.ALLOWED_ORIGINS ?? 'http://localhost:3000')
  .split(',')
  .map(o => o.trim())
  .filter(Boolean)

const app = Fastify({
  logger: isProd
    ? true
    : {
        transport: {
          target: 'pino-pretty',
          options: { colorize: true },
        },
      },
})

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
  methods: ['GET'],
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

try {
  await app.listen({ port, host: '0.0.0.0' })
  console.log(`API rodando em http://localhost:${port}`)
} catch (err) {
  app.log.error(err)
  process.exit(1)
}