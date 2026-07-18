import { ContentItemModel } from '../models/ContentItemModel';
import { UsageLogModel } from '../models/UsageLogModel';
import { getConfig } from '../lib/config';
import eventBus from './PipelineEventBus';
import fs from 'fs';
import path from 'path';
import { SchedulingService } from './SchedulingService';
import { TelegramService } from './TelegramService';
import { supabase } from '../lib/supabase';

export class ImageGeneratorService {
  static async startImageGeneration(itemId: string): Promise<void> {
    const item = await ContentItemModel.getById(itemId);
    if (!item || !item.image_prompt) return;

    const apiKey = process.env.AI33PRO_API_KEY;
    if (!apiKey) {
      await this.failItem(itemId, "AI33PRO_API_KEY not configured.");
      return;
    }

    try {
      const config = getConfig();
      
      const formData = new FormData();
      formData.append('prompt', item.image_prompt);
      formData.append('model_id', config.image_generation.model_id);
      formData.append('generations_count', '1');
      if (config.image_generation.model_parameters) {
        formData.append('model_parameters', JSON.stringify(config.image_generation.model_parameters));
      }

      // The prompt deliberately references @img1. AI33PRO binds that token to
      // the first multipart `assets` file, so the reference image must travel
      // with every generation request rather than merely being named in config.
      const referencePath = path.resolve(process.cwd(), config.image_generation.reference_image);
      if (!fs.existsSync(referencePath)) {
        throw new Error(`Reference image not found: ${config.image_generation.reference_image}`);
      }
      const referenceBuffer = fs.readFileSync(referencePath);
      const referenceBlob = new Blob([referenceBuffer], { type: 'image/png' });
      formData.append('assets', referenceBlob, path.basename(referencePath));

      const response = await fetch('https://api.ai33.pro/v1i/task/generate-image', {
        method: 'POST',
        headers: {
          'xi-api-key': apiKey
        },
        body: formData as any
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`API error ${response.status}: ${errText}`);
      }

      const data = await response.json();
      const taskId = data.task_id;
      
      await UsageLogModel.log({
        provider: 'ai33pro',
        endpoint: '/v1i/task/generate-image',
        credit_cost: data.credit_cost || null,
        success: 1,
        error_msg: null
      });

      const updatedItem = await ContentItemModel.update(itemId, { ai33pro_task_id: taskId });
      if (updatedItem) eventBus.emit('content_item_updated', updatedItem);
      
      // Start polling asynchronously
      setTimeout(() => this.pollTaskStatus(taskId, itemId), 15000);

    } catch (error: any) {
       await UsageLogModel.log({
        provider: 'ai33pro',
        endpoint: '/v1i/task/generate-image',
        credit_cost: null,
        success: 0,
        error_msg: error.message
      });
      await this.failItem(itemId, `Image Generation failed: ${error.message}`);
    }
  }

  static async pollTaskStatus(taskId: string, itemId: string, attempts = 0): Promise<void> {
    if (attempts > 100) { // approx 5 mins if 3s apart
      await this.failItem(itemId, "Image Generation timed out");
      return;
    }

    const apiKey = process.env.AI33PRO_API_KEY;
    if (!apiKey) return;

    try {
      const response = await fetch(`https://api.ai33.pro/v1/task/${taskId}`, {
        headers: {
          'xi-api-key': apiKey
        }
      });

      if (!response.ok) {
        throw new Error(`API error ${response.status}`);
      }

      const data = await response.json();
      
      if (data.status === 'done') {
        // Keep the raw completed response available in server logs while validating API payloads.
        console.info('AI33PRO completed task response:', JSON.stringify(data));
        const imageUrl = data.metadata?.image_url || data.metadata?.images?.[0]?.url || data.metadata?.output_url;
        if (!imageUrl) {
          throw new Error('Task completed but metadata contained no supported image URL.');
        }

        const imgResponse = await fetch(imageUrl);
        if (!imgResponse.ok) throw new Error('Failed to download image from result URL.');
        const imgBuffer = await imgResponse.arrayBuffer();
        
        const fileName = `${taskId}.png`;
        const { data: uploadData, error: uploadError } = await supabase.storage.from('post-images').upload(fileName, imgBuffer, {
          contentType: 'image/png',
          upsert: true
        });

        if (uploadError) throw new Error(`Supabase Storage upload failed: ${uploadError.message}`);
        
        const { data: { publicUrl } } = supabase.storage.from('post-images').getPublicUrl(fileName);

        const automation = getConfig().automation;
        const updatedItem = await ContentItemModel.update(itemId, { 
          status: automation.approval_mode === 'auto' ? 'preview_approved' : 'preview_pending', 
          image_local_path: publicUrl 
        });
        if (updatedItem) eventBus.emit('content_item_updated', updatedItem);
        if (updatedItem && automation.approval_mode === 'auto') await SchedulingService.scheduleAutomatic(itemId);
        if (updatedItem && automation.approval_mode === 'telegram') void TelegramService.notifyStatusChange(updatedItem);

      } else if (data.status === 'failed' || data.status === 'error') {
        throw new Error(data.error || 'Task failed');
      } else {
        // still running or queued
        setTimeout(() => this.pollTaskStatus(taskId, itemId, attempts + 1), 15000);
      }
    } catch (error: any) {
      await this.failItem(itemId, `Polling failed: ${error.message}`);
    }
  }

  static async regenerateImage(itemId: string): Promise<void> {
    const item = await ContentItemModel.update(itemId, { status: 'generating_image', image_local_path: null, ai33pro_task_id: null });
    if (item) eventBus.emit('content_item_updated', item);
    await this.startImageGeneration(itemId);
  }

  private static async failItem(itemId: string, msg: string) {
    const updated = await ContentItemModel.update(itemId, { status: 'failed', error_message: msg });
    if (updated) eventBus.emit('content_item_updated', updated);
  }
}
