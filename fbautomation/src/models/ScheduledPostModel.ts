import { supabase } from '../lib/supabase';
import { ScheduledPost } from '../lib/types';

export class ScheduledPostModel {
  static async create(data: Partial<ScheduledPost> & { id: string, content_item_id: string, target_region: string, scheduled_time_utc: string, status: string }): Promise<ScheduledPost> {
    const { data: result, error } = await supabase.from('scheduled_posts').insert(data).select().single();
    if (error) throw new Error(error.message);
    return result;
  }

  static async getById(id: string): Promise<ScheduledPost | null> {
    const { data, error } = await supabase.from('scheduled_posts').select('*').eq('id', id).single();
    if (error) return null;
    return data;
  }

  static async getDuePosts(nowUtc: Date): Promise<ScheduledPost[]> {
    const nowIso = nowUtc.toISOString();
    const { data, error } = await supabase.from('scheduled_posts').select('*').eq('status', 'pending').lte('scheduled_time_utc', nowIso);
    if (error) return [];
    return data || [];
  }

  static async updateStatus(id: string, status: string): Promise<void> {
    await supabase.from('scheduled_posts').update({ status }).eq('id', id);
  }

  static async getPostsWithin24h(nowUtc: Date): Promise<ScheduledPost[]> {
    const nowIso = nowUtc.toISOString();
    const next24h = new Date(nowUtc.getTime() + 24 * 60 * 60 * 1000).toISOString();
    const { data, error } = await supabase.from('scheduled_posts').select('*').gte('scheduled_time_utc', nowIso).lte('scheduled_time_utc', next24h);
    if (error) return [];
    return data || [];
  }

  static async getPostsForUtcDay(day: Date): Promise<ScheduledPost[]> {
    const start = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate())).toISOString();
    const end = new Date(Date.parse(start) + 24 * 60 * 60 * 1000).toISOString();
    const { data, error } = await supabase.from('scheduled_posts').select('*').gte('scheduled_time_utc', start).lt('scheduled_time_utc', end);
    if (error) return [];
    return data || [];
  }

  static async getLastScheduledPost(): Promise<ScheduledPost | null> {
    const { data, error } = await supabase.from('scheduled_posts').select('*').order('scheduled_time_utc', { ascending: false }).limit(1).single();
    if (error) return null;
    return data;
  }
}
