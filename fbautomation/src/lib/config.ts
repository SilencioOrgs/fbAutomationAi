import fs from 'fs';
import path from 'path';

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
  scheduling: {
    min_interval_minutes: number;
    max_posts_per_24h: number;
    regions: Record<string, RegionConfig>;
  };
}

const CONFIG_PATH = path.join(process.cwd(), 'config', 'prompt-templates.json');

export function getConfig(): AppConfig {
  const fileContent = fs.readFileSync(CONFIG_PATH, 'utf-8');
  return JSON.parse(fileContent) as AppConfig;
}

export function saveConfig(config: AppConfig): void {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
}
