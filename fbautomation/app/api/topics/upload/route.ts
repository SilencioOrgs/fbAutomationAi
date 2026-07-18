import { NextResponse } from 'next/server';
import * as xlsx from 'xlsx';
import { getConfig } from '@/src/lib/config';
import { TopicSourceService } from '@/src/services/TopicSourceService';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get('file');
    if (!(file instanceof File) || !file.name.toLowerCase().endsWith('.xlsx')) {
      return NextResponse.json({ error: 'Please upload an .xlsx file.' }, { status: 400 });
    }
    const buffer = Buffer.from(await file.arrayBuffer());
    const workbook = xlsx.read(buffer, { type: 'buffer' });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    const rows = xlsx.utils.sheet_to_json<unknown[]>(sheet, { header: 1, defval: '' });
    const headers = (rows[0] ?? []).map(String);
    const missing = getConfig().topic_source.required_columns.filter((column) => !headers.includes(column));
    if (missing.length) {
      return NextResponse.json({ error: `Invalid spreadsheet. Missing required columns: ${missing.join(', ')}` }, { status: 400 });
    }
    await TopicSourceService.processUploadedFile(buffer, file.name);
    return NextResponse.json({ ok: true });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Unable to import spreadsheet.' }, { status: 500 });
  }
}
