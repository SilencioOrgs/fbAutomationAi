import { getDb } from './db';
import { TopicSourceRow } from '../lib/types';
import crypto from 'crypto';

export class TopicSourceRowModel {
  static getUnconsumed(limit: number, offset: number): TopicSourceRow[] {
    const db = getDb();
    return db.prepare('SELECT * FROM topic_source_rows WHERE consumed = 0 ORDER BY row_index ASC LIMIT ? OFFSET ?')
             .all(limit, offset) as TopicSourceRow[];
  }

  static getByIds(ids: string[]): TopicSourceRow[] {
    if (ids.length === 0) return [];
    const db = getDb();
    const placeholders = ids.map(() => '?').join(', ');
    return db.prepare(`SELECT * FROM topic_source_rows WHERE id IN (${placeholders})`).all(...ids) as TopicSourceRow[];
  }

  static markConsumed(id: string): void {
    const db = getDb();
    db.prepare("UPDATE topic_source_rows SET consumed = 1, consumed_at = datetime('now') WHERE id = ?").run(id);
  }

  static hasUnconsumed(): boolean {
    const db = getDb();
    const row = db.prepare('SELECT 1 FROM topic_source_rows WHERE consumed = 0 LIMIT 1').get();
    return !!row;
  }

  static clearAndInsert(fileName: string, rows: Omit<TopicSourceRow, 'id' | 'consumed' | 'consumed_at' | 'created_at'>[]): void {
    const db = getDb();
    
    const insertMany = db.transaction((items) => {
      // Typically we'd clear the old table completely or keep history. The prompt implies "Excel file stays untouched, consumption tracked in DB".
      // Let's assume we delete all unconsumed rows to replace with the new file's content, or just clear everything.
      // Usually uploading a new file replaces the active pipeline topics. Let's delete all existing rows from the previous file to be safe.
      db.prepare('DELETE FROM topic_source_rows').run();

      const stmt = db.prepare(`
        INSERT INTO topic_source_rows (id, file_name, row_index, topic, subject, headline, fact_text, highlight_1, highlight_2, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      for (const item of items) {
        const id = crypto.randomUUID();
        stmt.run(
          id,
          fileName,
          item.row_index,
          item.topic,
          item.subject,
          item.headline,
          item.fact_text,
          item.highlight_1,
          item.highlight_2,
          item.category
        );
      }
    });

    insertMany(rows);
  }
}
