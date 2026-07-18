import { getDb } from './db';
import { UsageLog } from '../lib/types';
import crypto from 'crypto';

export class UsageLogModel {
  static log(data: Omit<UsageLog, 'id' | 'timestamp'>): void {
    const db = getDb();
    const id = crypto.randomUUID();
    const sql = `
      INSERT INTO usage_log (id, provider, endpoint, credit_cost, success, error_msg)
      VALUES (?, ?, ?, ?, ?, ?)
    `;
    db.prepare(sql).run(id, data.provider, data.endpoint, data.credit_cost, data.success, data.error_msg);
  }

  static getRecentLogs(limit: number): UsageLog[] {
    const db = getDb();
    return db.prepare('SELECT * FROM usage_log ORDER BY timestamp DESC LIMIT ?').all(limit) as UsageLog[];
  }
}
