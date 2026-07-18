import { NextResponse } from 'next/server';
import { ScheduleController } from '../@/src/controllers/ScheduleController';

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  try {
    const { region } = await request.json();
    if (!region) {
      return NextResponse.json({ error: 'region is required' }, { status: 400 });
    }
    const result = await ScheduleController.selectRegion(params.id, region);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
