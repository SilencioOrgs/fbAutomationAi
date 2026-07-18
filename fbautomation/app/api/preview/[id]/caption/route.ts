import { NextResponse } from 'next/server';
import { PreviewController } from '@/src/controllers/PreviewController';

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  try {
    const { caption } = await request.json();
    const result = await PreviewController.updateCaption(params.id, caption);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
