import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';
import { getConfig } from '../lib/config';
import { TopicSourceRowModel } from './TopicSourceRowModel';
import { TopicSourceService } from '../services/TopicSourceService';

let dbInstance: Database.Database | null = null;

export function getDb(): Database.Database {
  if (dbInstance) {
    return dbInstance;
  }

  const dbPath = process.env.DATABASE_PATH || './data/content.db';
  const dataDir = path.dirname(dbPath);

  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  
  const imagesDir = path.join(dataDir, 'images');
  if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
  }

  dbInstance = new Database(dbPath);
  dbInstance.pragma('journal_mode = WAL');

  // Initialize schema
  dbInstance.exec(`
    CREATE TABLE IF NOT EXISTS content_items (
      id TEXT PRIMARY KEY,
      topic TEXT,
      subject TEXT,
      headline TEXT,
      fact_text TEXT,
      highlight_1 TEXT,
      highlight_2 TEXT,
      category TEXT,
      status TEXT NOT NULL,
      generated_title TEXT,
      generated_description TEXT,
      generated_hashtags TEXT,
      image_local_path TEXT,
      image_prompt TEXT,
      ai33pro_task_id TEXT,
      fb_post_id TEXT,
      telegram_msg_id TEXT,
      telegram_chat_id TEXT,
      error_message TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS topic_source_rows (
      id TEXT PRIMARY KEY,
      file_name TEXT NOT NULL,
      row_index INTEGER NOT NULL,
      topic TEXT,
      subject TEXT,
      headline TEXT,
      fact_text TEXT,
      highlight_1 TEXT,
      highlight_2 TEXT,
      category TEXT,
      consumed INTEGER DEFAULT 0,
      consumed_at DATETIME,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(file_name, row_index)
    );

    CREATE TABLE IF NOT EXISTS scheduled_posts (
      id TEXT PRIMARY KEY,
      content_item_id TEXT NOT NULL,
      target_region TEXT NOT NULL,
      scheduled_time_utc DATETIME NOT NULL,
      status TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(content_item_id) REFERENCES content_items(id)
    );

    CREATE TABLE IF NOT EXISTS usage_log (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      endpoint TEXT NOT NULL,
      credit_cost REAL,
      success INTEGER NOT NULL,
      error_msg TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  // Seed only a genuinely new database. Uploaded files continue to replace rows explicitly.
  if (TopicSourceRowModel.isEmpty()) {
    const activeFile = getConfig().topic_source.active_file;
    const sourcePath = path.resolve(process.cwd(), activeFile);
    if (fs.existsSync(sourcePath)) {
      void TopicSourceService.processUploadedFile(fs.readFileSync(sourcePath), activeFile)
        .catch((error) => console.error('Initial topic source import failed:', error));
    }
  }

  return dbInstance;
}
