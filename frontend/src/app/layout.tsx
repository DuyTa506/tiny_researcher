import type { Metadata } from 'next';
import { Inter, Merriweather } from 'next/font/google';
import Providers from './providers';
import './globals.css';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
});

const merriweather = Merriweather({
  variable: '--font-merriweather',
  subsets: ['latin'],
  weight: ['300', '400', '700'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Research Assistant — AI-Powered Paper Discovery',
  description:
    'An intelligent research paper aggregation and analysis system. Collect, screen, extract evidence, and synthesize citation-grounded reports.',
  keywords: [
    'research',
    'papers',
    'AI',
    'academic',
    'analysis',
    'citations',
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${merriweather.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
