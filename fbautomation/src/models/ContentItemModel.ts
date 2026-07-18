import { supabase } from '../lib/supabase';
import { ContentItem } from '../lib/types';

export class ContentItemModel {
  static async getById(id: string): Promise<ContentItem | null> {
    const { data, error } = await supabase.from('content_items').select('*').eq('id', id).single();
    if (error) return null;
    return data;
  }

  static async create(data: Partial<ContentItem> & { id: string, status: string }): Promise<ContentItem> {
    const { data: result, error } = await supabase.from('content_items').insert(data).select().single();
    if (error) throw new Error(error.message);
    return result;
  }

  static async update(id: string, updates: Partial<ContentItem>): Promise<ContentItem | null> {
    const keys = Object.keys(updates).filter(k => k !== 'id' && k !== 'created_at');
    if (keys.length === 0) return await this.getById(id);
    
    const updateData = { ...updates, updated_at: new Date().toISOString() };
    const { data: result, error } = await supabase.from('content_items').update(updateData).eq('id', id).select().single();
    if (error) return null;
    return result;
  }

  static async getByStatus(status: string): Promise<ContentItem[]> {
    const { data, error } = await supabase.from('content_items').select('*').eq('status', status).order('created_at', { ascending: true });
    if (error) return [];
    return data || [];
  }
}
