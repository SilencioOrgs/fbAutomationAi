import { NextResponse } from 'next/server';

export async function GET() {
  const key = process.env.AI33PRO_API_KEY;
  if (!key) return NextResponse.json({ error: 'AI33PRO_API_KEY is not configured.' }, { status: 503 });
  const response = await fetch('https://api.ai33.pro/v1/credits', { headers: { 'xi-api-key': key }, cache: 'no-store' });
  const body = await response.text();
  if (!response.ok) return NextResponse.json({ error: `AI33PRO credits lookup failed: ${body}` }, { status: response.status });
  return new NextResponse(body, { headers: { 'Content-Type': 'application/json' } });
}
