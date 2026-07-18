import { ScheduledPostModel } from '../models/ScheduledPostModel';
import { ContentItemModel } from '../models/ContentItemModel';
import { FacebookPublisherService } from './FacebookPublisherService';
import { getConfig } from '../lib/config';
import crypto from 'crypto';
import eventBus from './PipelineEventBus';

export class SchedulingService {
  static suggestSlot(regionName: string): Date {
    const config = getConfig();
    const region = config.scheduling.regions[regionName];
    if (!region) throw new Error(`Region ${regionName} not found in config`);

    const now = new Date();
    // Simplified logic for MVP: just find the next available slot that respects min_interval and max_posts
    // Real implementation would use region.timezone and region.peak_hours to find the precise window.
    
    const lastPost = ScheduledPostModel.getLastScheduledPost();
    
    let suggestedTime = new Date();
    // At least min_interval_minutes from now
    suggestedTime.setMinutes(suggestedTime.getMinutes() + config.scheduling.min_interval_minutes);
    
    if (lastPost) {
      const lastPostTime = new Date(lastPost.scheduled_time_utc);
      const minNextTime = new Date(lastPostTime.getTime() + config.scheduling.min_interval_minutes * 60000);
      if (suggestedTime < minNextTime) {
        suggestedTime = minNextTime;
      }
    }

    // In a full implementation, we'd adjust suggestedTime to fit inside region.peak_hours using region.timezone
    return suggestedTime;
  }

  static schedulePost(itemId: string, region: string, scheduledTimeUtc: Date): void {
    const updatedItem = ContentItemModel.update(itemId, { status: 'scheduled' });
    
    if (updatedItem) {
      ScheduledPostModel.create({
        id: crypto.randomUUID(),
        content_item_id: itemId,
        target_region: region,
        scheduled_time_utc: scheduledTimeUtc.toISOString(),
        status: 'pending'
      });
      eventBus.emit('content_item_updated', updatedItem);
    }
  }

  static async processDuePosts(): Promise<void> {
    const now = new Date();
    const duePosts = ScheduledPostModel.getDuePosts(now);
    
    for (const post of duePosts) {
      // Mark publishing
      ScheduledPostModel.updateStatus(post.id, 'publishing');
      let item = ContentItemModel.update(post.content_item_id, { status: 'publishing' });
      if (item) eventBus.emit('content_item_updated', item);
      
      const fbPostId = await FacebookPublisherService.publish(post.content_item_id);
      
      if (fbPostId) {
        ScheduledPostModel.updateStatus(post.id, 'published');
        // FacebookPublisherService handles updating content_item status to published
      } else {
        ScheduledPostModel.updateStatus(post.id, 'failed');
        // FacebookPublisherService handles updating content_item status to failed
      }
    }
  }
}
