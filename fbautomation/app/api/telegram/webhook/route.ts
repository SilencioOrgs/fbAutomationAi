import { NextResponse } from 'next/server';
import { TelegramService } from '@/src/services/TelegramService';
import { PreviewController } from '@/src/controllers/PreviewController';

export async function POST(request: Request) {
  const secretToken = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
  const expectedSecret = process.env.TELEGRAM_WEBHOOK_SECRET;

  if (expectedSecret && secretToken !== expectedSecret) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const payload = await request.json();
    
    // We parse basic callbacks from telegram here
    if (payload.callback_query) {
      const data = payload.callback_query.data;
      const messageId = payload.callback_query.message.message_id;
      const chatId = payload.callback_query.message.chat.id;

      if (data.startsWith('approve_')) {
        const id = data.replace('approve_', '');
        await PreviewController.approve(id);
        await TelegramService.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
      } else if (data.startsWith('reject_')) {
        const id = data.replace('reject_', '');
        await PreviewController.reject(id);
        await TelegramService.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
      } else if (data.startsWith('regen_')) {
        const id = data.replace('regen_', '');
        await PreviewController.regenerateImage(id);
        await TelegramService.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
      }
    } else {
      await TelegramService.handleWebhook(payload);
    }
    
    return NextResponse.json({ ok: true });
  } catch (error: any) {
    console.error('Webhook error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
