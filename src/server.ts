import Fastify from 'fastify'
import cors from '@fastify/cors'
import searchRoute   from './routes/search.js'
import booksRoute    from './routes/books.js'
import chaptersRoute from './routes/chapters.js'
import povsRoute     from './routes/povs.js'

const app = Fastify({
  logger: {
    transport: {
      target: 'pino-pretty',
      options: { colorize: true },
    },
  },
})

await app.register(cors, { origin: '*' })

await app.register(searchRoute)
await app.register(booksRoute)
await app.register(chaptersRoute)
await app.register(povsRoute)

app.get('/health', async () => ({
  status: 'ok',
  timestamp: new Date().toISOString(),
}))

app.setErrorHandler((error, _req, reply) => {
  app.log.error(error)
  reply.status(500).send({ error: 'Erro interno do servidor.' })
})

try {
  await app.listen({ port: 3000, host: '0.0.0.0' })
  console.log('API rodando em http://localhost:3000')
} catch (err) {
  app.log.error(err)
  process.exit(1)
}