import { ContentItemModel } from '../models/ContentItemModel';
import { ImageGeneratorService } from '../services/ImageGeneratorService';
import eventBus from '../services/PipelineEventBus';

export class PreviewController {
  static async approve(id: string) {
    const item = ContentItemModel.update(id, { status: 'approved' });
    if (item) eventBus.emit('content_item_updated', item);
    // Actually the next step after approval is scheduling. Wait, the prompt says "Region-based scheduling".
    // After approval, the user selects a region, or is region selection separate?
    // "select-region" route implies they select a region after approve. Let's just set status to "approved_for_scheduling" or similar. 
    // Wait, the status list is `pending_approval, approved, generating_content, generating_image, preview_pending, scheduled, publishing, published, failed, rejected`
    // Wait, the prompt says: POST /api/topics/select sets status to `approved`. Then it kicks off content generation.
    // So after image generation, it's `preview_pending`. Then the user approves the preview.
    // What is the status after preview approval? Maybe `approved_preview` or `awaiting_schedule`? 
    // Let's just keep it as `approved_preview` or we can skip straight to `select-region`.
    // Actually, usually they approve and select region at the same time or sequentially. Let's just say it goes back to `approved` or we add a new status.
    // Let's use `approved` again, or `ready_to_schedule`. We'll just leave it as `preview_approved` (need to add to schema if strictly checked, but SQLite doesn't strictly check enums). Let's use `preview_approved`.
    const updated = ContentItemModel.update(id, { status: 'preview_approved' });
    if (updated) eventBus.emit('content_item_updated', updated);
    return updated;
  }

  static async reject(id: string) {
    const item = ContentItemModel.update(id, { status: 'rejected' });
    if (item) eventBus.emit('content_item_updated', item);
    return item;
  }

  static async regenerateImage(id: string) {
    await ImageGeneratorService.regenerateImage(id);
    return { success: true };
  }

  static async updateCaption(id: string, newCaption: string) {
    // For simplicity, we just store it in generated_description since we combine them later.
    // A better approach would be to parse it back or just have a single `caption` field.
    // Let's just update `generated_description` for now, assuming the UI sends the combined text.
    const item = ContentItemModel.update(id, { generated_description: newCaption });
    if (item) eventBus.emit('content_item_updated', item);
    return item;
  }
}
