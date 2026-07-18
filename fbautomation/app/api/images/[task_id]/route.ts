import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: Request, context: { params: Promise<{ task_id: string }> }) {
  const params = await context.params;
  const taskId = params.task_id.replace('.png', '');
  const dbPath = process.env.DATABASE_PATH || './data/content.db';
  const dataDir = path.dirname(dbPath);
  const imagePath = path.join(dataDir, 'images', `${taskId}.png`);

  if (!fs.existsSync(imagePath)) {
    return new NextResponse('Image not found', { status: 404 });
  }

  const imageBuffer = fs.readFileSync(imagePath);
  
  return new NextResponse(imageBuffer, {
    headers: {
      'Content-Type': 'image/png',
      'Cache-Control': 'public, max-age=31536000, immutable',
    },
  });
}
