import { NextResponse } from 'next/server';
import { TopicController } from '@/src/controllers/TopicController';

export async function POST(request: Request) {
  try {
    const { ids } = await request.json();
    if (!Array.isArray(ids)) {
      return NextResponse.json({ error: 'ids must be an array' }, { status: 400 });
    }

    const result = await TopicController.selectTopics(ids);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
