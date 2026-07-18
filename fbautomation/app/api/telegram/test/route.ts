import { NextResponse } from 'next/server';
import { TelegramService } from '@/src/services/TelegramService';

export async function POST() {
  if (!process.env.TELEGRAM_BOT_TOKEN || !process.env.TELEGRAM_ADMIN_ID) return NextResponse.json({ error: 'Telegram bot token or admin ID is not configured.' }, { status: 503 });
  await TelegramService.sendMessage('Pipeline test message: Telegram notifications are connected.');
  return NextResponse.json({ ok: true });
}
