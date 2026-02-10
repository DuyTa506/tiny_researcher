'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  FileText,
  Filter,
  BookOpen,
  Microscope,
  TrendingUp,
  Clock,
  ArrowRight,
  Inbox,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import { paperService } from '@/services/papers';
import { reportService } from '@/services/reports';
import { conversationService } from '@/services/conversations';
import { formatDate } from '@/lib/utils';
import styles from './styles.module.css';

// Mock activity data for chart (will be replaced by real data)
const activityData = [
  { day: 'Mon', papers: 4, reports: 1 },
  { day: 'Tue', papers: 7, reports: 2 },
  { day: 'Wed', papers: 12, reports: 1 },
  { day: 'Thu', papers: 8, reports: 3 },
  { day: 'Fri', papers: 15, reports: 2 },
  { day: 'Sat', papers: 6, reports: 1 },
  { day: 'Sun', papers: 3, reports: 0 },
];

export default function DashboardPage() {
  const papers = useQuery({
    queryKey: ['papers'],
    queryFn: () => paperService.list().then((r) => r.data),
  });

  const reports = useQuery({
    queryKey: ['reports'],
    queryFn: () => reportService.list().then((r) => r.data),
  });

  const sessions = useQuery({
    queryKey: ['conversations'],
    queryFn: () => conversationService.list().then((r) => r.data),
  });

  const totalPapers = papers.data?.total ?? 0;
  const screenedPapers = papers.data?.items?.filter(
    (p) => p.status !== 'RAW'
  ).length ?? 0;
  const totalReports = reports.data?.total ?? 0;
  const sessionsList = (sessions.data as Record<string, string>[] | undefined) ?? [];
  const activeSessions = sessionsList.filter(
    (s) => s.state === 'EXECUTING'
  ).length;

  return (
    <AppShell title="Dashboard">
      {/* Hero */}
      <div className={styles.hero}>
        <h2 className={styles.heroTitle}>Research Assistant</h2>
        <p className={styles.heroSubtitle}>
          AI-powered paper discovery, evidence extraction, and citation-grounded
          report synthesis.
        </p>
        <Link href="/research">
          <Button variant="secondary" size="lg">
            <Microscope size={18} />
            Start New Research
            <ArrowRight size={16} />
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className={styles.grid}>
        <Card glass>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.papers}`}>
              <FileText size={22} />
            </div>
            <div>
              {papers.isLoading ? (
                <Skeleton width={60} height={36} />
              ) : (
                <div className={styles.statValue}>{totalPapers}</div>
              )}
              <div className={styles.statLabel}>Total Papers</div>
            </div>
          </div>
        </Card>

        <Card glass>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.screened}`}>
              <Filter size={22} />
            </div>
            <div>
              {papers.isLoading ? (
                <Skeleton width={60} height={36} />
              ) : (
                <div className={styles.statValue}>{screenedPapers}</div>
              )}
              <div className={styles.statLabel}>Screened</div>
            </div>
          </div>
        </Card>

        <Card glass>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.reports}`}>
              <BookOpen size={22} />
            </div>
            <div>
              {reports.isLoading ? (
                <Skeleton width={60} height={36} />
              ) : (
                <div className={styles.statValue}>{totalReports}</div>
              )}
              <div className={styles.statLabel}>Reports</div>
            </div>
          </div>
        </Card>

        <Card glass>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.active}`}>
              <TrendingUp size={22} />
            </div>
            <div>
              {sessions.isLoading ? (
                <Skeleton width={60} height={36} />
              ) : (
                <div className={styles.statValue}>{activeSessions}</div>
              )}
              <div className={styles.statLabel}>Active Research</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Two columns: Activity Chart + Recent Sessions */}
      <div className={styles.columns}>
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>Weekly Activity</h3>
          </div>
          <Card className={styles.chartCard}>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={activityData}>
                <defs>
                  <linearGradient id="gradPapers" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradReports" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="day"
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border)' }}
                />
                <YAxis
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border)' }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontSize: '13px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="papers"
                  stroke="var(--primary)"
                  fillOpacity={1}
                  fill="url(#gradPapers)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="reports"
                  stroke="var(--accent)"
                  fillOpacity={1}
                  fill="url(#gradReports)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>Recent Sessions</h3>
            <Link href="/research">
              <Button variant="ghost" size="sm">
                View All <ArrowRight size={14} />
              </Button>
            </Link>
          </div>
          <Card>
            {sessions.isLoading ? (
              <div className={styles.sessionList}>
                {[1, 2, 3].map((i) => (
                  <div key={i} className={styles.sessionItem}>
                    <Skeleton variant="circle" width={8} height={8} />
                    <div style={{ flex: 1 }}>
                      <Skeleton variant="text" width="80%" />
                      <Skeleton variant="text" width="40%" />
                    </div>
                  </div>
                ))}
              </div>
            ) : !sessionsList.length ? (
              <div className={styles.empty}>
                <Inbox size={40} className={styles.emptyIcon} />
                <p className={styles.emptyText}>No research sessions yet</p>
              </div>
            ) : (
              <div className={styles.sessionList}>
                {sessionsList.slice(0, 5).map((session: Record<string, string>) => (
                  <Link
                    key={session.conversation_id || session.id}
                    href={`/research?id=${session.conversation_id || session.id}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <div className={styles.sessionItem}>
                      <div
                        className={`${styles.sessionDot} ${session.state === 'EXECUTING'
                            ? styles.active
                            : styles.idle
                          }`}
                      />
                      <div className={styles.sessionInfo}>
                        <div className={styles.sessionTopic}>
                          {session.current_topic || session.topic || 'Untitled Research'}
                        </div>
                        <div className={styles.sessionDate}>
                          <Clock size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                          {formatDate(session.created_at)}
                        </div>
                      </div>
                      <Badge
                        variant={
                          session.state === 'COMPLETE' ? 'high' : 'info'
                        }
                      >
                        {session.state}
                      </Badge>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
