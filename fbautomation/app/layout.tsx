import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import { Sidebar } from '@/src/components/Sidebar';
import { getConfig } from '@/src/lib/config';

const poppins = Poppins({
  weight: ['400', '500', '600', '700'],
  subsets: ["latin"],
  variable: "--font-poppins",
});

export const metadata: Metadata = {
  title: "FB Automation",
  description: "Content automation pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const config = getConfig();
  return (
    <html lang="en" className="dark">
      <body
        className={`${poppins.variable} font-sans bg-black text-gray-200 antialiased min-h-screen`}
      >
        <div className="flex min-h-screen"><Sidebar pageName={config.branding.page_name} telegramConnected={!!process.env.TELEGRAM_BOT_TOKEN}/><main className="h-screen min-w-0 flex-1 overflow-y-auto">{children}</main></div>
      </body>
    </html>
  );
}
