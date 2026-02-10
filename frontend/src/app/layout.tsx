import type { Metadata } from 'next';
import { Crimson_Pro, Atkinson_Hyperlegible } from 'next/font/google';
import Providers from './providers';
import './globals.css';

const crimsonPro = Crimson_Pro({
  variable: '--font-heading',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

const atkinson = Atkinson_Hyperlegible({
  variable: '--font-body',
  subsets: ['latin'],
  weight: ['400', '700'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Tiny Researcher — AI-Powered Paper Discovery',
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
      <body className={`${crimsonPro.variable} ${atkinson.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
