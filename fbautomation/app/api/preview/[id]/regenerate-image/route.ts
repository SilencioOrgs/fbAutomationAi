import { NextResponse } from 'next/server';
import { PreviewController } from '@/src/controllers/PreviewController';

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  try {
    const result = await PreviewController.regenerateImage(params.id);
    return NextResponse.json(result);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
