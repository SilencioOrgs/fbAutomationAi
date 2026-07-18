import { getDb } from './db';
import { ContentItem } from '../lib/types';

export class ContentItemModel {
  static getById(id: string): ContentItem | null {
    const db = getDb();
    const row = db.prepare('SELECT * FROM content_items WHERE id = ?').get(id) as ContentItem | undefined;
    return row || null;
  }

  static create(data: Partial<ContentItem> & { id: string, status: string }): ContentItem {
    const db = getDb();
    const keys = Object.keys(data);
    const values = Object.values(data);
    const placeholders = keys.map(() => '?').join(', ');
    
    const sql = `INSERT INTO content_items (${keys.join(', ')}) VALUES (${placeholders})`;
    db.prepare(sql).run(...values);
    
    return this.getById(data.id) as ContentItem;
  }

  static update(id: string, updates: Partial<ContentItem>): ContentItem | null {
    const db = getDb();
    const keys = Object.keys(updates).filter(k => k !== 'id' && k !== 'created_at');
    if (keys.length === 0) return this.getById(id);
    
    keys.push('updated_at');
    const updateData = { ...updates, updated_at: new Date().toISOString() };
    
    const setClause = keys.map(k => `${k} = ?`).join(', ');
    const values = keys.map(k => (updateData as any)[k]);
    values.push(id);
    
    const sql = `UPDATE content_items SET ${setClause} WHERE id = ?`;
    db.prepare(sql).run(...values);
    
    return this.getById(id);
  }

  static getByStatus(status: string): ContentItem[] {
    const db = getDb();
    return db.prepare('SELECT * FROM content_items WHERE status = ? ORDER BY created_at ASC').all(status) as ContentItem[];
  }
}
