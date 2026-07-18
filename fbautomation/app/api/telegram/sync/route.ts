import { NextResponse } from 'next/server';
import { getConfig } from '@/src/lib/config';
import { ContentItemModel } from '@/src/models/ContentItemModel';
import { TelegramService } from '@/src/services/TelegramService';

export async function POST() {
  const token = process.env.TELEGRAM_BOT_TOKEN; const baseUrl = process.env.NEXT_PUBLIC_APP_URL;
  if (!token || !baseUrl) return NextResponse.json({ error: 'TELEGRAM_BOT_TOKEN or NEXT_PUBLIC_APP_URL is not configured.' }, { status: 503 });
  const webhook = `${baseUrl.replace(/\/$/, '')}/api/telegram/webhook`;
  const response = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: webhook, secret_token: process.env.TELEGRAM_WEBHOOK_SECRET }) });
  if (!response.ok) return NextResponse.json({ error: 'Telegram webhook registration failed.' }, { status: 502 });
  if (!getConfig().telegram_sync_enabled) return NextResponse.json({ resent: 0, webhook });
  const pending = await ContentItemModel.getByStatus('preview_pending');
  for (const item of pending) await TelegramService.sendPreview(item);
  return NextResponse.json({ resent: pending.length, webhook });
}
