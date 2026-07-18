import * as xlsx from 'xlsx';
import { TopicSourceRowModel } from '../models/TopicSourceRowModel';
import { ContentItemModel } from '../models/ContentItemModel';
import { TopicSourceRow, ContentItem } from '../lib/types';
import eventBus from './PipelineEventBus';
import crypto from 'crypto';
import { getConfig } from '../lib/config';

export class TopicSourceService {
  static async processUploadedFile(fileBuffer: Buffer, fileName: string): Promise<void> {
    const workbook = xlsx.read(fileBuffer, { type: 'buffer' });
    const firstSheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[firstSheetName];
    
    const requiredColumns = getConfig().topic_source.required_columns;
    const data = xlsx.utils.sheet_to_json(worksheet, { defval: '' }) as any[];
    const headers = data.length > 0 ? Object.keys(data[0]) : [];
    const missingColumns = requiredColumns.filter((column) => !headers.includes(column));
    if (missingColumns.length > 0) {
      throw new Error(`Missing required columns: ${missingColumns.join(', ')}`);
    }
    
    const rowsToInsert = data.map((row, index) => ({
      file_name: fileName,
      row_index: index + 2, // 1-based, plus header row
      topic: String(row.Topic || ''),
      subject: String(row.Subject || ''),
      headline: String(row.Headline || ''),
      fact_text: String(row.Fact_Text || ''),
      highlight_1: String(row.Highlight_1 || ''),
      highlight_2: String(row.Highlight_2 || ''),
      category: String(row.Category || '')
    }));

    TopicSourceRowModel.clearAndInsert(fileName, rowsToInsert);
  }

  static getAvailableTopics(page: number, pageSize: number): { topics: TopicSourceRow[], hasMore: boolean } {
    const limit = pageSize;
    const offset = (page - 1) * pageSize;
    
    const topics = TopicSourceRowModel.getUnconsumed(limit + 1, offset);
    const hasMore = topics.length > limit;
    
    return {
      topics: topics.slice(0, limit),
      hasMore
    };
  }

  static async consumeTopics(ids: string[]): Promise<ContentItem[]> {
    const rows = TopicSourceRowModel.getByIds(ids);
    const createdItems: ContentItem[] = [];

    for (const row of rows) {
      if (row.consumed) continue;
      
      TopicSourceRowModel.markConsumed(row.id);
      
      const newItem = ContentItemModel.create({
        id: crypto.randomUUID(),
        topic: row.topic,
        subject: row.subject,
        headline: row.headline,
        fact_text: row.fact_text,
        highlight_1: row.highlight_1,
        highlight_2: row.highlight_2,
        category: row.category,
        status: 'approved'
      });
      
      createdItems.push(newItem);
      
      eventBus.emit('content_item_updated', newItem);
    }

    return createdItems;
  }
}
