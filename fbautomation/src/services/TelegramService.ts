import { ContentItemModel } from '../models/ContentItemModel';
import { ContentItem } from '../lib/types';
import fs from 'fs';
import eventBus from './PipelineEventBus';

export class TelegramService {
  static async handleWebhook(payload: any): Promise<void> {
    // This will be called from the route handler after verifying secret
    if (!payload.callback_query) return;
    
    const callbackQuery = payload.callback_query;
    const data = callbackQuery.data; // e.g., "approve_ID", "reject_ID"
    const chatId = callbackQuery.message.chat.id;

    // We leave the actual action routing to the controller that calls this, 
    // or we can just parse here. Usually the controller calls PreviewController.approve etc.
    // The prompt says "routed to the same controller actions", so the route handler will do the routing.
    // So this service is mostly for SENDING messages to Telegram.
  }

  static async notifyStatusChange(item: ContentItem): Promise<void> {
    if (item.status === 'preview_pending') {
      await this.sendPreview(item);
    } else if (item.status === 'failed') {
      await this.sendMessage(`Pipeline Error for "${item.headline}": ${item.error_message}`);
    } else if (item.status === 'published') {
      await this.sendMessage(`Published: ${item.headline}\nFB Post ID: ${item.fb_post_id}`);
    }
  }

  static async sendPreview(item: ContentItem): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    const adminId = process.env.TELEGRAM_ADMIN_ID;
    if (!token || !adminId || !item.image_local_path || !fs.existsSync(item.image_local_path)) return;

    const caption = `Preview Ready:\n\n${item.generated_title}\n\n${item.generated_description}\n\n${item.generated_hashtags}`;
    
    const replyMarkup = {
      inline_keyboard: [
        [
          { text: 'Approve', callback_data: `approve_${item.id}` },
          { text: 'Reject', callback_data: `reject_${item.id}` }
        ],
        [
          { text: 'Regenerate Image', callback_data: `regen_${item.id}` }
        ]
      ]
    };

    try {
      const formData = new FormData();
      formData.append('chat_id', adminId);
      formData.append('caption', caption.substring(0, 1024));
      formData.append('reply_markup', JSON.stringify(replyMarkup));
      
      const fileBuffer = fs.readFileSync(item.image_local_path);
      const fileBlob = new Blob([fileBuffer], { type: 'image/png' });
      formData.append('photo', fileBlob, 'image.png');

      const response = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
        method: 'POST',
        body: formData as any
      });

      if (response.ok) {
        const data = await response.json();
        ContentItemModel.update(item.id, { 
          telegram_msg_id: data.result.message_id.toString(),
          telegram_chat_id: adminId
        });
      }
    } catch (error) {
      console.error('Telegram sendPreview error', error);
    }
  }

  static async sendMessage(text: string): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    const adminId = process.env.TELEGRAM_ADMIN_ID;
    if (!token || !adminId) return;

    try {
      await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: adminId, text })
      });
    } catch (error) {
      console.error('Telegram sendMessage error', error);
    }
  }
  
  static async updateMessageReplyMarkup(chatId: string, messageId: string, replyMarkup: any): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) return;
    
    try {
      await fetch(`https://api.telegram.org/bot${token}/editMessageReplyMarkup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, message_id: messageId, reply_markup: replyMarkup })
      });
    } catch (error) {
      console.error('Telegram update message error', error);
    }
  }
}
