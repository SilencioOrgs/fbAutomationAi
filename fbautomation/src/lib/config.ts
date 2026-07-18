import fs from 'fs';
import path from 'path';
import { supabase } from './supabase';

export interface RegionConfig {
  timezone: string;
  peak_hours_local: [string, string][];
}

export interface AppConfig {
  branding: {
    page_name: string;
    page_avatar_initial: string;
  };
  content_generation: {
    title_template: string;
    description_template: string;
    hashtags_template: string;
  };
  image_generation: {
    prompt_template: string;
    model_id: string;
    model_parameters: Record<string, any>;
    reference_image: string;
  };
  topic_source: {
    required_columns: string[];
    active_file: string;
  };
  telegram_sync_enabled: boolean;
  automation: {
    approval_mode: 'auto' | 'telegram';
    schedule_mode: 'peak_hours' | 'fixed_daily_time';
    daily_upload_time: string;
    daily_upload_timezone: string;
  };
  scheduling: {
    min_interval_minutes: number;
    max_posts_per_24h: number;
    regions: Record<string, RegionConfig>;
  };
}

const FALLBACK_CONFIG_PATH = path.join(process.cwd(), 'config', 'prompt-templates.json');
let cachedConfig: AppConfig | null = null;
let lastCacheTime = 0;

export async function getConfig(forceRefresh = false): Promise<AppConfig> {
  // Use memory cache to avoid hitting Supabase too frequently (cache for 1 min)
  if (!forceRefresh && cachedConfig && Date.now() - lastCacheTime < 60000) {
    return cachedConfig;
  }

  const { data, error } = await supabase.from('app_config').select('config_data').eq('id', 'global').single();
  
  if (data && data.config_data) {
    cachedConfig = data.config_data as AppConfig;
    lastCacheTime = Date.now();
    return cachedConfig;
  }

  // If Supabase is empty (first run), fallback to local JSON and seed it
  let fallbackConfig: AppConfig;
  try {
    const fileContent = fs.readFileSync(FALLBACK_CONFIG_PATH, 'utf-8');
    fallbackConfig = JSON.parse(fileContent) as AppConfig;
  } catch (e) {
    throw new Error('Local fallback config is missing or invalid.');
  }

  // Seed Supabase silently in background (will fail if RLS not disabled but that's fine, we return fallback)
  supabase.from('app_config').insert({ id: 'global', config_data: fallbackConfig }).then();

  cachedConfig = fallbackConfig;
  lastCacheTime = Date.now();
  return fallbackConfig;
}

export async function saveConfig(config: AppConfig): Promise<void> {
  const { error } = await supabase.from('app_config').upsert({ id: 'global', config_data: config });
  if (error) {
    throw new Error(`Failed to save config to Supabase: ${error.message}`);
  }
  cachedConfig = config;
  lastCacheTime = Date.now();
}
