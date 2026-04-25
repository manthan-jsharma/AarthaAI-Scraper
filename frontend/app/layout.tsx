import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bangalore Broker Rankings",
  description: "AI-powered digital presence ranking for real estate brokers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a0a] text-white antialiased min-h-screen">{children}</body>
    </html>
  );
}
