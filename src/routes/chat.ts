import { FastifyInstance } from 'fastify'

interface ChatBody {
  messages: { role: string; content: string }[]
}

interface MicroserviceSource {
  book: string
  chapter: string
  pov: string
  distance: number
}

interface MicroserviceResponse {
  answer: string
  sources: MicroserviceSource[]
}

const RAG_MICROSERVICE_URL = process.env.RAG_MICROSERVICE_URL
const RAG_API_KEY = process.env.RAG_API_KEY

export default async function chatRoute(app: FastifyInstance) {
  app.post<{ Body: ChatBody }>('/api/chat', async (req, reply) => {
    const { messages } = req.body

    if (!messages || messages.length === 0) {
      return reply.status(400).send({ error: 'Nenhuma mensagem enviada.' })
    }

    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUserMsg || !lastUserMsg.content.trim()) {
      return reply.status(400).send({ error: 'Nenhuma pergunta do usuário encontrada.' })
    }

    const question = lastUserMsg.content.trim()
    if (question.length < 2) {
      return reply.status(400).send({ error: 'A pergunta deve ter ao menos 2 caracteres.' })
    }

    if (!RAG_MICROSERVICE_URL) {
      return reply.status(500).send({
        reply: {
          id: `chat_${Date.now()}`,
          role: 'assistant',
          content: 'Perdoe-me, não consegui consultar os pergaminhos agora.',
          timestamp: Date.now(),
        },
      })
    }

    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 120000)

      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (RAG_API_KEY) {
        headers['Authorization'] = `Bearer ${RAG_API_KEY}`
      }

      const response = await fetch(`${RAG_MICROSERVICE_URL}/api/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ question }),
        signal: controller.signal,
      })

      clearTimeout(timeout)

      if (!response.ok) {
        throw new Error(`Microsserviço retornou status ${response.status}`)
      }

      const data: MicroserviceResponse = await response.json()

      return {
        reply: {
          id: `chat_${Date.now()}`,
          role: 'assistant',
          content: data.answer,
          sources: data.sources?.map(s => ({
            book_title: s.book,
            chapter_title: s.chapter,
            pov: s.pov,
          })),
          timestamp: Date.now(),
        },
      }
    } catch (error) {
      app.log.error(error)
      return reply.status(500).send({
        reply: {
          id: `chat_${Date.now()}`,
          role: 'assistant',
          content: 'Perdoe-me, não consegui consultar os pergaminhos agora.',
          timestamp: Date.now(),
        },
      })
    }
  })
}
