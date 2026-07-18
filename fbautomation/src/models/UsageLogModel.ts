import { supabase } from '../lib/supabase';
import { UsageLog } from '../lib/types';
import crypto from 'crypto';

export class UsageLogModel {
  static async log(data: Omit<UsageLog, 'id' | 'timestamp'>): Promise<void> {
    const id = crypto.randomUUID();
    await supabase.from('usage_log').insert({ id, ...data });
  }

  static async getRecentLogs(limit: number): Promise<UsageLog[]> {
    const { data, error } = await supabase.from('usage_log').select('*').order('timestamp', { ascending: false }).limit(limit);
    if (error) return [];
    return data || [];
  }
}
