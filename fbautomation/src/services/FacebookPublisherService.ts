import { ContentItemModel } from '../models/ContentItemModel';
import eventBus from './PipelineEventBus';
import fs from 'fs';

export class FacebookPublisherService {
  static async publish(itemId: string): Promise<string | null> {
    const item = await ContentItemModel.getById(itemId);
    if (!item) return null;

    const accessToken = process.env.FB_PAGE_ACCESS_TOKEN;
    const pageId = process.env.FB_PAGE_ID;

    if (!accessToken || !pageId) {
      await this.failItem(itemId, "Facebook credentials not configured.");
      return null;
    }

    if (!item.image_local_path) {
      await this.failItem(itemId, "Image URL not found.");
      return null;
    }

    const caption = [
      item.generated_title,
      '',
      item.generated_description,
      '',
      item.generated_hashtags
    ].filter(s => s != null).join('\n');

    try {
      const formData = new FormData();
      formData.append('access_token', accessToken);
      formData.append('message', caption);
      
      if (item.image_local_path.startsWith('http')) {
        // We now store the public URL in image_local_path
        formData.append('url', item.image_local_path);
      } else {
        // Fallback for older locally generated files (if any still exist during transition)
        const fileBuffer = fs.readFileSync(item.image_local_path);
        const fileBlob = new Blob([fileBuffer], { type: 'image/png' });
        formData.append('source', fileBlob, 'image.png');
      }

      const response = await fetch(`https://graph.facebook.com/v19.0/${pageId}/photos`, {
        method: 'POST',
        body: formData as any
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(`FB API error: ${errData.error?.message || response.statusText}`);
      }

      const data = await response.json();
      const fbPostId = data.id || data.post_id;

      const updatedItem = await ContentItemModel.update(itemId, { 
        status: 'published',
        fb_post_id: fbPostId
      });
      if (updatedItem) eventBus.emit('content_item_updated', updatedItem);
      
      return fbPostId;
    } catch (error: any) {
      await this.failItem(itemId, `Facebook publish failed: ${error.message}`);
      return null;
    }
  }

  private static async failItem(itemId: string, msg: string) {
    const updated = await ContentItemModel.update(itemId, { status: 'failed', error_message: msg });
    if (updated) eventBus.emit('content_item_updated', updated);
  }
}
