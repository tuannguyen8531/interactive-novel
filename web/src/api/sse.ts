import type { SseEvent } from './types'

export interface SseHandlers {
  onEvent?: (event: SseEvent) => void
  onError?: (error: Error) => void
  onOpen?: () => void
  onClose?: () => void
}

export interface SseClient {
  close: () => void
}

interface SseOptions {
  token?: string | null
  lastEventId?: string | null
  signal?: AbortSignal
}

function parseEventBlock(block: string): SseEvent | null {
  let id: string | null = null
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split(/\r\n|\r|\n/)) {
    if (line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator === -1 ? line : line.slice(0, separator)
    const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'id') id = value
    if (field === 'event') event = value || 'message'
    if (field === 'data') dataLines.push(value)
  }
  if (dataLines.length === 0) return null
  return { id, event, data: dataLines.join('\n') }
}

export function openSse(url: string, handlers: SseHandlers, options: SseOptions = {}): SseClient {
  const controller = new AbortController()
  const abortFromCaller = () => controller.abort()
  options.signal?.addEventListener('abort', abortFromCaller, { once: true })
  const headers = new Headers({ Accept: 'text/event-stream' })
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`)
  if (options.lastEventId) headers.set('Last-Event-ID', options.lastEventId)

  let closed = false
  let closeNotified = false
  const notifyClose = () => {
    if (closeNotified) return
    closeNotified = true
    handlers.onClose?.()
  }
  const run = async (): Promise<void> => {
    try {
      const response = await fetch(url, { headers, signal: controller.signal })
      if (!response.ok || !response.body) {
        throw new Error(`SSE request failed: ${response.status} ${response.statusText}`)
      }
      handlers.onOpen?.()
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!closed) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let separatorIndex = buffer.search(/\r\n\r\n|\n\n|\r\r/)
        while (separatorIndex >= 0) {
          const separator = buffer.match(/\r\n\r\n|\n\n|\r\r/)?.[0] ?? '\n\n'
          const block = buffer.slice(0, separatorIndex)
          buffer = buffer.slice(separatorIndex + separator.length)
          const event = parseEventBlock(block)
          if (event) handlers.onEvent?.(event)
          separatorIndex = buffer.search(/\r\n\r\n|\n\n|\r\r/)
        }
      }
      if (!closed) notifyClose()
    } catch (error) {
      if (!closed && !(error instanceof DOMException && error.name === 'AbortError')) {
        handlers.onError?.(error instanceof Error ? error : new Error(String(error)))
      }
    } finally {
      options.signal?.removeEventListener('abort', abortFromCaller)
    }
  }
  void run()

  return {
    close: () => {
      if (closed) return
      closed = true
      controller.abort()
      notifyClose()
    }
  }
}
