import { afterEach, describe, expect, it, vi } from 'vitest'
import { openSse } from '@/api/sse'

describe('SSE client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses ordered events and forwards the replay cursor', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('id: 1\nevent: job_queued\ndata: {"step":1}\n\n'))
        controller.enqueue(encoder.encode('id: 2\nevent: writer_token\ndata: {"step":2}\n\n'))
        controller.close()
      }
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const events: string[] = []
    const closed = new Promise<void>((resolve) => {
      openSse(
        '/api/jobs/job-1/events',
        {
          onEvent: (event) => events.push(`${event.id}:${event.event}:${event.data}`),
          onClose: resolve
        },
        { lastEventId: '0' }
      )
    })

    await closed

    expect(events).toEqual(['1:job_queued:{"step":1}', '2:writer_token:{"step":2}'])
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(requestInit.headers).get('Last-Event-ID')).toBe('0')
  })
})
