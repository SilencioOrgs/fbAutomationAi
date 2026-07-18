import { NextResponse } from 'next/server';
import { ScheduleController } from '@/src/controllers/ScheduleController';

export async function GET() {
  try {
    const result = await ScheduleController.processTick();
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
