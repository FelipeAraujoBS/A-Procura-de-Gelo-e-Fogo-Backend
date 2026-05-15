import Database from 'better-sqlite3'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DB_PATH = path.resolve(__dirname, '../database.db')

const db = new Database(DB_PATH, {
  readonly: true,
  fileMustExist: true,
})

export default db