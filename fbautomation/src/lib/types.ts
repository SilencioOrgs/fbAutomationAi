export interface ContentItem {
  id: string;
  topic: string;
  subject: string;
  headline: string;
  fact_text: string;
  highlight_1: string;
  highlight_2: string;
  category: string;
  fb_title: string | null;
  fb_description: string | null;
  fb_hashtags: string | null;
  status: string; // pending_approval, approved, generating_content, generating_image, preview_pending, scheduled, publishing, published, failed, rejected
  generated_title: string | null;
  generated_description: string | null;
  generated_hashtags: string | null;
  image_local_path: string | null;
  image_prompt: string | null;
  ai33pro_task_id: string | null;
  fb_post_id: string | null;
  telegram_msg_id: string | null;
  telegram_chat_id: string | null;
  error_message: string | null;
  planned_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface TopicSourceRow {
  id: string;
  file_name: string;
  row_index: number;
  topic: string;
  subject: string;
  headline: string;
  fact_text: string;
  highlight_1: string;
  highlight_2: string;
  category: string;
  fb_title: string | null;
  fb_description: string | null;
  fb_hashtags: string | null;
  consumed: number; // 0 or 1
  consumed_at: string | null;
  created_at: string;
}

export interface ScheduledPost {
  id: string;
  content_item_id: string;
  target_region: string;
  scheduled_time_utc: string;
  status: string; // pending, published, failed
  created_at: string;
}

export interface UsageLog {
  id: string;
  provider: string;
  endpoint: string;
  credit_cost: number | null;
  success: number; // 0 or 1
  error_msg: string | null;
  timestamp: string;
}
