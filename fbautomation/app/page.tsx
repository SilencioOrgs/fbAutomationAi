import { HomeDashboard } from '@/src/components/HomeDashboard';
import { ContentItemModel } from '@/src/models/ContentItemModel';

export const dynamic = 'force-dynamic';
export default async function Home() {
  const statuses = ['pending_approval', 'approved', 'generating_content', 'generating_image', 'preview_pending', 'preview_approved', 'scheduled', 'publishing'];
  const nestedItems = await Promise.all(statuses.map(status => ContentItemModel.getByStatus(status)));
  const items = nestedItems.flat().slice(0, 50);
  return <HomeDashboard initialItems={items}/>;
}
