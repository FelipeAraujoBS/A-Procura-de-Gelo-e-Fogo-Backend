import sanitizeHtml from 'sanitize-html'

export function sanitizeSnippet(raw: string): string {
  return sanitizeHtml(raw, {
    allowedTags: ['mark'],
    allowedAttributes: {},
    disallowedTagsMode: 'discard',
  })
}