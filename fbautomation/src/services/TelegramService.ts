import { ContentItemModel } from '../models/ContentItemModel';
import { ContentItem } from '../lib/types';
import fs from 'fs';
import eventBus from './PipelineEventBus';
import { getConfig, saveConfig } from '../lib/config';
import { TopicController } from '../controllers/TopicController';
import { FacebookPublisherService } from './FacebookPublisherService';
import { PreviewController } from '../controllers/PreviewController';

export class TelegramService {
  static async handleWebhook(payload: any): Promise<void> {
    // This will be called from the route handler after verifying secret
    if (!payload.callback_query) return;
    
    const callbackQuery = payload.callback_query;
    const data = callbackQuery.data; // e.g., "approve_ID", "reject_ID"
    const chatId = callbackQuery.message.chat.id;
  }

  static async handleGenerateCommand(chatId: string, count: number, messageId?: string): Promise<void> {
    const startMsg = `⏳ Generating ${count} topic(s)... This may take a minute.`;
    if (messageId) {
      await this.editMessageText(chatId, messageId, startMsg);
    } else {
      await this.sendMessageToChat(chatId, startMsg);
    }

    const { topics } = await TopicController.getAvailableTopics(1, count);
    if (topics.length === 0) {
      const emptyMsg = "⚠️ No available topics found in the database. Please upload a new Excel file.";
      if (messageId) {
        await this.editMessageText(chatId, messageId, emptyMsg);
      } else {
        await this.sendMessageToChat(chatId, emptyMsg);
      }
      return;
    }
    const ids = topics.map((t: any) => t.id);
    const today = new Date().toISOString().split('T')[0];
    await TopicController.selectTopics(ids, today);
  }

  static async showGenerateMenu(chatId: string): Promise<void> {
    const keyboard = {
      inline_keyboard: [
        [
          { text: '1️⃣', callback_data: 'gcount_1' },
          { text: '2️⃣', callback_data: 'gcount_2' },
          { text: '3️⃣', callback_data: 'gcount_3' },
          { text: '4️⃣', callback_data: 'gcount_4' }
        ]
      ]
    };
    await this.sendMessageToChatWithMarkup(chatId, "How many topics do you want to generate today?", keyboard);
  }

  static async handlePostCommand(itemId: string, chatId: string, messageId: string): Promise<void> {
    await this.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
    await this.sendMessageToChat(chatId, "⏳ Publishing to Facebook...");
    
    const fbPostId = await FacebookPublisherService.publish(itemId);
    if (fbPostId) {
      await this.sendMessageToChat(chatId, `✅ Successfully posted to Facebook! (Post ID: ${fbPostId})`);
    } else {
      const item = await ContentItemModel.getById(itemId);
      await this.sendMessageToChat(chatId, `⚠️ Failed to post to Facebook: ${item?.error_message || 'Unknown error. Check if FB_PAGE_ACCESS_TOKEN is configured.'}`);
    }
  }

  static async showModelSelection(itemId: string, chatId: string, messageId: string): Promise<void> {
    const models = [
      'bytedance-seedream-4.5',
      'openai-dall-e-3',
      'midjourney-v6'
    ]; // Can be fetched from config or API, hardcoding popular ones for simplicity

    const keyboard = models.map(m => ([{ text: m, callback_data: `setmod_${itemId}_${m}` }]));
    keyboard.push([{ text: 'Cancel', callback_data: `approve_${itemId}` }]); // Revert back

    await this.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: keyboard });
  }

  static async handleModelSelection(itemId: string, modelId: string, chatId: string, messageId: string): Promise<void> {
    const config = getConfig();
    config.image_generation.model_id = modelId;
    saveConfig(config);

    await this.updateMessageReplyMarkup(chatId, messageId, { inline_keyboard: [] });
    await this.sendMessageToChat(chatId, `✅ Model changed to ${modelId}. Regenerating image...`);
    await PreviewController.regenerateImage(itemId);
  }

  static async sendMessageToChat(chatId: string, text: string): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) return;
    try {
      await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text })
      });
    } catch (error) {
      console.error('Telegram sendMessageToChat error', error);
    }
  }

  static async sendMessageToChatWithMarkup(chatId: string, text: string, reply_markup: any): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) return;
    try {
      await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text, reply_markup })
      });
    } catch (error) {
      console.error('Telegram sendMessageToChatWithMarkup error', error);
    }
  }

  static async editMessageText(chatId: string, messageId: string, text: string): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) return;
    try {
      await fetch(`https://api.telegram.org/bot${token}/editMessageText`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, message_id: messageId, text })
      });
    } catch (error) {
      console.error('Telegram editMessageText error', error);
    }
  }

  static async notifyStatusChange(item: ContentItem): Promise<void> {
    if (!getConfig().telegram_sync_enabled) return;
    if (item.status === 'preview_pending') {
      await this.sendPreview(item);
    } else if (item.status === 'failed') {
      await this.sendMessage(`Pipeline Error for "${item.headline}": ${item.error_message}`);
    } else if (item.status === 'published') {
      await this.sendMessage(`Published: ${item.headline}\nFB Post ID: ${item.fb_post_id}`);
    }
  }

  static async sendPreview(item: ContentItem): Promise<void> {
    if (!getConfig().telegram_sync_enabled) return;
    const token = process.env.TELEGRAM_BOT_TOKEN;
    const adminId = process.env.TELEGRAM_ADMIN_ID;
    if (!token || !adminId || !item.image_local_path || !fs.existsSync(item.image_local_path)) return;

    const caption = `Preview Ready:\n\n${item.generated_title}\n\n${item.generated_description}\n\n${item.generated_hashtags}`;
    
    const replyMarkup = {
      inline_keyboard: [
        [
          { text: 'Post to Facebook', callback_data: `post_${item.id}` }
        ],
        [
          { text: 'Approve', callback_data: `approve_${item.id}` },
          { text: 'Reject', callback_data: `reject_${item.id}` }
        ],
        [
          { text: 'Regenerate Image', callback_data: `regen_${item.id}` },
          { text: 'Change Model', callback_data: `models_${item.id}` }
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
