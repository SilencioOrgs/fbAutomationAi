import { TopicSourceService } from '../services/TopicSourceService';
import { ContentGeneratorService } from '../services/ContentGeneratorService';
import { ImageGeneratorService } from '../services/ImageGeneratorService';

export class TopicController {
  static async getAvailableTopics(page: number, pageSize: number = 20) {
    return await TopicSourceService.getAvailableTopics(page, pageSize);
  }

  static async selectTopics(ids: string[], plannedDate?: string, startGeneration: boolean = true, initialStatus: string = 'approved') {
    // 1. Mark as consumed, create ContentItems
    const createdItems = await TopicSourceService.consumeTopics(ids, plannedDate, initialStatus);
    
    // 2. Kick off content + image generation for each
    if (startGeneration) {
      for (const item of createdItems) {
        // Async generation pipeline
        (async () => {
          await ContentGeneratorService.generateContent(item.id);
          await ImageGeneratorService.startImageGeneration(item.id);
        })().catch(console.error);
      }
    }

    return { success: true, count: createdItems.length, items: createdItems };
  }
}
