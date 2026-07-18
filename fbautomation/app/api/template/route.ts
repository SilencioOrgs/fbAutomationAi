import fs from 'fs';
import path from 'path';
import { NextResponse } from 'next/server';
import { getConfig } from '@/src/lib/config';

export const runtime = 'nodejs';

export async function GET() {
  const filePath = path.resolve(process.cwd(), getConfig().image_generation.reference_image);
  if (!fs.existsSync(filePath)) return new NextResponse('Reference template not found.', { status: 404 });
  return new NextResponse(fs.readFileSync(filePath), { headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=3600' } });
}
