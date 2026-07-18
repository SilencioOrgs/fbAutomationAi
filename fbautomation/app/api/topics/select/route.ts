import { NextResponse } from 'next/server';
import { TopicController } from '@/src/controllers/TopicController';

export async function POST(request: Request) {
  try {
    const { ids, plannedDate } = await request.json();
    if (!Array.isArray(ids)) {
      return NextResponse.json({ error: 'ids must be an array' }, { status: 400 });
    }

    if (plannedDate !== undefined && (typeof plannedDate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(plannedDate))) {
      return NextResponse.json({ error: 'plannedDate must be YYYY-MM-DD' }, { status: 400 });
    }
    const result = await TopicController.selectTopics(ids, plannedDate);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
