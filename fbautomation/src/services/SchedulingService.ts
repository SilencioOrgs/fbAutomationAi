import { ScheduledPostModel } from '../models/ScheduledPostModel';
import { ContentItemModel } from '../models/ContentItemModel';
import { FacebookPublisherService } from './FacebookPublisherService';
import { getConfig } from '../lib/config';
import crypto from 'crypto';
import eventBus from './PipelineEventBus';

export class SchedulingService {
  private static fixedTimeForDay(dateText: string, time: string, timezone: string): Date {
    const [year, month, day] = dateText.split('-').map(Number); const [hour, minute] = time.split(':').map(Number);
    const desiredUtc = Date.UTC(year, month - 1, day, hour, minute);
    const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    const parts = Object.fromEntries(formatter.formatToParts(new Date(desiredUtc)).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
    const renderedUtc = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour), Number(parts.minute));
    return new Date(desiredUtc - (renderedUtc - desiredUtc));
  }

  static async scheduleAutomatic(itemId: string): Promise<void> {
    const item = await ContentItemModel.getById(itemId); if (!item) return;
    const config = getConfig(); let time: Date;
    if (config.automation.schedule_mode === 'fixed_daily_time') {
      const baseDate = item.planned_date || new Date().toISOString().slice(0, 10);
      time = this.fixedTimeForDay(baseDate, config.automation.daily_upload_time, config.automation.daily_upload_timezone);
      if (time < new Date()) time = this.fixedTimeForDay(new Date().toISOString().slice(0, 10), config.automation.daily_upload_time, config.automation.daily_upload_timezone);
      
      let posts = await ScheduledPostModel.getPostsForUtcDay(time);
      while (posts.length >= config.scheduling.max_posts_per_24h) {
        time = new Date(time.getTime() + 24 * 60 * 60 * 1000);
        posts = await ScheduledPostModel.getPostsForUtcDay(time);
      }
    } else {
      time = await this.suggestSlot('Global');
    }
    await this.schedulePost(itemId, 'Global', time);
  }

  static async suggestSlot(regionName: string): Promise<Date> {
    const config = getConfig();
    const region = config.scheduling.regions[regionName];
    if (!region) throw new Error(`Region ${regionName} not found in config`);

    const now = new Date();
    // Simplified logic for MVP: just find the next available slot that respects min_interval and max_posts
    // Real implementation would use region.timezone and region.peak_hours to find the precise window.
    
    const lastPost = await ScheduledPostModel.getLastScheduledPost();
    
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

  static async schedulePost(itemId: string, region: string, scheduledTimeUtc: Date): Promise<void> {
    const updatedItem = await ContentItemModel.update(itemId, { status: 'scheduled' });
    
    if (updatedItem) {
      await ScheduledPostModel.create({
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
    const duePosts = await ScheduledPostModel.getDuePosts(now);
    
    for (const post of duePosts) {
      // Mark publishing
      await ScheduledPostModel.updateStatus(post.id, 'publishing');
      let item = await ContentItemModel.update(post.content_item_id, { status: 'publishing' });
      if (item) eventBus.emit('content_item_updated', item);
      
      const fbPostId = await FacebookPublisherService.publish(post.content_item_id);
      
      if (fbPostId) {
        await ScheduledPostModel.updateStatus(post.id, 'published');
        // FacebookPublisherService handles updating content_item status to published
      } else {
        await ScheduledPostModel.updateStatus(post.id, 'failed');
        // FacebookPublisherService handles updating content_item status to failed
      }
    }
  }
}
