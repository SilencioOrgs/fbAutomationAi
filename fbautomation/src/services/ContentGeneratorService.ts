import { ContentItemModel } from '../models/ContentItemModel';
import { getConfig } from '../lib/config';
import eventBus from './PipelineEventBus';

export class ContentGeneratorService {
  static async generateContent(itemId: string): Promise<void> {
    const item = await ContentItemModel.getById(itemId);
    if (!item) return;

    // Update status to generating_content
    let updatedItem = await ContentItemModel.update(itemId, { status: 'generating_content' });
    if (updatedItem) eventBus.emit('content_item_updated', updatedItem);

    try {
      const config = await getConfig();
      const contentTemplates = config.content_generation;
      const imageTemplates = config.image_generation;

      // Simple interpolation replacement
      const interpolate = (template: string, data: any) => {
        if (!template) return '';
        return template.replace(/\{([a-zA-Z0-9_]+)\}/gi, (match, key) => {
          const lowerKey = key.toLowerCase();
          return data[lowerKey] !== undefined ? data[lowerKey] : match;
        });
      };

      const context = {
        topic: item.topic,
        subject: item.subject,
        headline: item.headline,
        fact_text: item.fact_text,
        highlight_1: item.highlight_1,
        highlight_2: item.highlight_2,
        category: item.category
      };

      const generatedTitle = item.fb_title || interpolate(contentTemplates.title_template, context);
      const generatedDescription = item.fb_description || interpolate(contentTemplates.description_template, context);
      const generatedHashtags = item.fb_hashtags || interpolate(contentTemplates.hashtags_template, context);
      const imagePrompt = interpolate(imageTemplates.prompt_template, context);

      updatedItem = await ContentItemModel.update(itemId, {
        generated_title: generatedTitle,
        generated_description: generatedDescription,
        generated_hashtags: generatedHashtags,
        image_prompt: imagePrompt,
        status: 'generating_image' // move to next step
      });

      if (updatedItem) eventBus.emit('content_item_updated', updatedItem);
    } catch (error: any) {
      const failedItem = await ContentItemModel.update(itemId, { 
        status: 'failed', 
        error_message: `Content Generation failed: ${error.message}`
      });
      if (failedItem) eventBus.emit('content_item_updated', failedItem);
    }
  }
}
