export interface Paragraph {
  book_number: number
  book_title: string
  chapter_number: number
  chapter_title: string
  pov: string
  paragraph_index: number
  text: string
}

export interface SearchResult extends Omit<Paragraph, 'text'> {
  snippet: string
}

export interface SearchResponse {
  query: string
  total: number
  limit: number
  offset: number
  results: SearchResult[]
}

export interface Book {
  book_number: number
  book_title: string
  chapter_count: number
  paragraph_count: number
}

export interface Chapter {
  chapter_number: number
  chapter_title: string
  pov: string
  paragraph_count: number
}

export interface Pov {
  pov: string
  chapter_count: number
  book_count: number
}