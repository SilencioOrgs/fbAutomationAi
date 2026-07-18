import { TopicSourceService } from '../services/TopicSourceService';
import { ContentGeneratorService } from '../services/ContentGeneratorService';
import { ImageGeneratorService } from '../services/ImageGeneratorService';

export class TopicController {
  static async getAvailableTopics(page: number, pageSize: number = 20) {
    return await TopicSourceService.getAvailableTopics(page, pageSize);
  }

  static async selectTopics(ids: string[], plannedDate?: string) {
    // 1. Mark as consumed, create ContentItems
    const createdItems = await TopicSourceService.consumeTopics(ids, plannedDate);
    
    // 2. Kick off content + image generation for each
    for (const item of createdItems) {
      // Async generation pipeline
      (async () => {
        await ContentGeneratorService.generateContent(item.id);
        // Image generation starts automatically if generation succeeds,
        // but we can call it manually if ContentGeneratorService just preps fields.
        // Actually ContentGeneratorService already triggers image_prompt generation and we should call ImageGeneratorService here to start it.
        // Let's modify ContentGeneratorService to not automatically start ImageGen, but do it here, or do it in ContentGeneratorService.
        // We set status to 'generating_image', so let's call ImageGeneratorService here.
        await ImageGeneratorService.startImageGeneration(item.id);
      })().catch(console.error);
    }

    return { success: true, count: createdItems.length };
  }
}
