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
      } else if (data.startsWith('post_')) {
        const id = data.replace('post_', '');
        await TelegramService.handlePostCommand(id, chatId, messageId);
      } else if (data.startsWith('models_')) {
        const id = data.replace('models_', '');
        await TelegramService.showModelSelection(id, chatId, messageId);
      } else if (data.startsWith('setmod_')) {
        const [id, ...modelParts] = data.replace('setmod_', '').split('_');
        const modelId = modelParts.join('_');
        await TelegramService.handleModelSelection(id, modelId, chatId, messageId);
      } else if (data.startsWith('gcount_')) {
        const count = parseInt(data.replace('gcount_', ''), 10);
        await TelegramService.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
        await TelegramService.handleGenerateCommand(chatId, count, messageId);
      }
    } else if (payload.message?.text) {
      const text = payload.message.text;
      const chatId = payload.message.chat.id;
      const match = text.match(/^\/generate\s+(\d+)$/i);
      if (match) {
        const count = parseInt(match[1], 10);
        await TelegramService.handleGenerateCommand(chatId, count);
      } else if (text.trim().toLowerCase() === '/generate') {
        await TelegramService.showGenerateMenu(chatId);
      } else {
        await TelegramService.handleWebhook(payload);
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
