import { NextResponse } from 'next/server';
import eventBus from '@/src/services/PipelineEventBus';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const listener = (item: any) => {
        try {
          const data = JSON.stringify(item);
          controller.enqueue(encoder.encode(`data: ${data}\n\n`));
        } catch (err) {
          console.error("SSE encoding error", err);
        }
      };

      eventBus.on('content_item_updated', listener);

      // Ping to keep connection alive
      const interval = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: ping\n\n`));
        } catch (err) {
          clearInterval(interval);
        }
      }, 15000);

      request.signal.addEventListener('abort', () => {
        eventBus.removeListener('content_item_updated', listener);
        clearInterval(interval);
      });
    }
  });

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
