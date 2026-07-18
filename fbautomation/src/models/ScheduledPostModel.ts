import { getDb } from './db';
import { ScheduledPost } from '../lib/types';

export class ScheduledPostModel {
  static create(data: Partial<ScheduledPost> & { id: string, content_item_id: string, target_region: string, scheduled_time_utc: string, status: string }): ScheduledPost {
    const db = getDb();
    const sql = `
      INSERT INTO scheduled_posts (id, content_item_id, target_region, scheduled_time_utc, status)
      VALUES (?, ?, ?, ?, ?)
    `;
    db.prepare(sql).run(data.id, data.content_item_id, data.target_region, data.scheduled_time_utc, data.status);
    
    return this.getById(data.id) as ScheduledPost;
  }

  static getById(id: string): ScheduledPost | null {
    const db = getDb();
    return db.prepare('SELECT * FROM scheduled_posts WHERE id = ?').get(id) as ScheduledPost | undefined || null;
  }

  static getDuePosts(nowUtc: Date): ScheduledPost[] {
    const db = getDb();
    const nowIso = nowUtc.toISOString();
    return db.prepare('SELECT * FROM scheduled_posts WHERE status = ? AND scheduled_time_utc <= ?').all('pending', nowIso) as ScheduledPost[];
  }

  static updateStatus(id: string, status: string): void {
    const db = getDb();
    db.prepare('UPDATE scheduled_posts SET status = ? WHERE id = ?').run(status, id);
  }

  static getPostsWithin24h(nowUtc: Date): ScheduledPost[] {
    const db = getDb();
    const nowIso = nowUtc.toISOString();
    const next24h = new Date(nowUtc.getTime() + 24 * 60 * 60 * 1000).toISOString();
    return db.prepare('SELECT * FROM scheduled_posts WHERE scheduled_time_utc >= ? AND scheduled_time_utc <= ?').all(nowIso, next24h) as ScheduledPost[];
  }

  static getLastScheduledPost(): ScheduledPost | null {
    const db = getDb();
    return db.prepare('SELECT * FROM scheduled_posts ORDER BY scheduled_time_utc DESC LIMIT 1').get() as ScheduledPost | undefined || null;
  }
}
