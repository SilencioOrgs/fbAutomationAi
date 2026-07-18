import { NextResponse } from 'next/server';
import { getConfig, saveConfig, AppConfig } from '@/src/lib/config';
import { TopicSourceRowModel } from '@/src/models/TopicSourceRowModel';

function validConfig(config: AppConfig): string | null {
  if (!config.branding.page_name.trim()) return 'Page name is required.';
  if (typeof config.telegram_sync_enabled !== 'boolean') return 'Telegram sync must be enabled or disabled.';
  if (!['auto', 'telegram'].includes(config.automation?.approval_mode)) return 'Approval mode must be auto or telegram.';
  if (!['peak_hours', 'fixed_daily_time'].includes(config.automation?.schedule_mode)) return 'Schedule mode is invalid.';
  if (!/^\d{2}:\d{2}$/.test(config.automation?.daily_upload_time || '') || !config.automation.daily_upload_timezone?.trim()) return 'A valid daily upload time and timezone are required.';
  if (!config.image_generation.model_id.trim()) return 'An image model is required.';
  const { aspect_ratio, resolution } = config.image_generation.model_parameters;
  if (typeof aspect_ratio !== 'string' || !aspect_ratio.trim() || typeof resolution !== 'string' || !resolution.trim()) return 'Image aspect ratio and resolution are required.';
  const s = config.scheduling;
  if (!Number.isInteger(s.min_interval_minutes) || s.min_interval_minutes < 1) return 'Minimum interval must be a positive integer.';
  if (!Number.isInteger(s.max_posts_per_24h) || s.max_posts_per_24h < 1) return 'Maximum posts must be a positive integer.';
  for (const [region, value] of Object.entries(s.regions)) {
    if (!region.trim() || !value.timezone.trim() || !Array.isArray(value.peak_hours_local) || value.peak_hours_local.some((window) => !Array.isArray(window) || window.length !== 2 || !window[0] || !window[1])) return 'Every region needs a timezone and valid start/end peak-hour windows.';
  }
  return null;
}

export async function GET() {
  const [config, topicSource] = await Promise.all([getConfig(), TopicSourceRowModel.getSummary()]);
  return NextResponse.json({ config, topicSource });
}

export async function PATCH(request: Request) {
  try {
    const config = await request.json() as AppConfig;
    const error = validConfig(config);
    if (error) return NextResponse.json({ error }, { status: 400 });
    await saveConfig(config);
    return NextResponse.json({ ok: true, config });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Invalid settings payload.' }, { status: 400 });
  }
}
