import { SettingsPanel } from '@/src/components/SettingsPanel';

export default function SettingsPage() {
  return <div className="mx-auto w-full max-w-4xl p-6"><div className="mb-6"><h1 className="text-xl font-semibold text-white">Settings</h1><p className="text-sm text-gray-500">Configure content, scheduling, and automation behavior.</p></div><SettingsPanel/></div>;
}
