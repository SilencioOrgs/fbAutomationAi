import { supabase } from '../lib/supabase';
import { TopicSourceRow } from '../lib/types';
import crypto from 'crypto';

export class TopicSourceRowModel {
  static async getUnconsumed(limit: number, offset: number): Promise<TopicSourceRow[]> {
    const { data, error } = await supabase
      .from('topic_source_rows')
      .select('*')
      .eq('consumed', 0)
      .order('row_index', { ascending: true })
      .range(offset, offset + limit - 1);
    
    if (error) return [];
    return data || [];
  }

  static async getByIds(ids: string[]): Promise<TopicSourceRow[]> {
    if (ids.length === 0) return [];
    const { data, error } = await supabase
      .from('topic_source_rows')
      .select('*')
      .in('id', ids);
    if (error) return [];
    return data || [];
  }

  static async markConsumed(id: string): Promise<void> {
    await supabase
      .from('topic_source_rows')
      .update({ consumed: 1, consumed_at: new Date().toISOString() })
      .eq('id', id);
  }

  static async hasUnconsumed(): Promise<boolean> {
    const { data, error } = await supabase
      .from('topic_source_rows')
      .select('id')
      .eq('consumed', 0)
      .limit(1);
    if (error) return false;
    return data && data.length > 0;
  }

  static async isEmpty(): Promise<boolean> {
    const { data, error } = await supabase
      .from('topic_source_rows')
      .select('id')
      .limit(1);
    if (error) return true;
    return !data || data.length === 0;
  }

  static async getSummary(): Promise<{ activeFile: string | null; remaining: number }> {
    const { data: activeData } = await supabase
      .from('topic_source_rows')
      .select('file_name')
      .order('created_at', { ascending: false })
      .limit(1);
    
    const { count } = await supabase
      .from('topic_source_rows')
      .select('*', { count: 'exact', head: true })
      .eq('consumed', 0);
      
    return { 
      activeFile: activeData?.[0]?.file_name ?? null, 
      remaining: count || 0 
    };
  }

  static async clearAndInsert(fileName: string, rows: Omit<TopicSourceRow, 'id' | 'consumed' | 'consumed_at' | 'created_at'>[]): Promise<void> {
    const { error: deleteError } = await supabase.from('topic_source_rows').delete().neq('id', '00000000-0000-0000-0000-000000000000');
    if (deleteError) throw new Error(`Delete error: ${deleteError.message}`);

    const insertPayload = rows.map(item => ({
      file_name: fileName,
      row_index: item.row_index,
      topic: item.topic,
      subject: item.subject,
      headline: item.headline,
      fact_text: item.fact_text,
      highlight_1: item.highlight_1,
      highlight_2: item.highlight_2,
      category: item.category,
      fb_title: item.fb_title,
      fb_description: item.fb_description,
      fb_hashtags: item.fb_hashtags
    }));

    const { error: insertError } = await supabase.from('topic_source_rows').insert(insertPayload);
    if (insertError) throw new Error(`Insert error: ${insertError.message}`);
  }
}
