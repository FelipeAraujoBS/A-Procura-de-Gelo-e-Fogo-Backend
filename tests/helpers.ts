import supertest from 'supertest'
import { buildApp, registerPlugins } from '../src/server.js'

export async function buildTestApp() {
  const app = buildApp({ logger: false })
  await registerPlugins(app)
  return app
}

export async function createTestClient() {
  const app = await buildTestApp()
  await app.ready()
  return supertest(app.server)
}