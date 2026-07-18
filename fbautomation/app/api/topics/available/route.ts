import { NextResponse } from 'next/server';
import { TopicController } from '@/src/controllers/TopicController';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get('page') || '1', 10);
  
  try {
    const result = await TopicController.getAvailableTopics(page);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
