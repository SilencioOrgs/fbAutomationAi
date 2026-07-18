import { SchedulingService } from '../services/SchedulingService';

export class ScheduleController {
  static async selectRegion(id: string, region: string) {
    const suggestedTime = SchedulingService.suggestSlot(region);
    SchedulingService.schedulePost(id, region, suggestedTime);
    return { success: true, scheduled_time_utc: suggestedTime };
  }

  static async processTick() {
    await SchedulingService.processDuePosts();
    return { success: true };
  }
}
