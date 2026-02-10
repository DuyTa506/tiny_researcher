'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    ArrowLeft,
    CheckCircle,
    AlertTriangle,
    FileText,
} from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Skeleton from '@/components/ui/Skeleton';
import { reportService } from '@/services/reports';
import { formatDate } from '@/lib/utils';
import type { TaxonomyMatrix } from '@/lib/types';
import styles from './styles.module.css';

function TaxonomyView({ matrix }: { matrix: TaxonomyMatrix }) {
    if (!matrix.themes.length) return null;

    return (
        <div className={styles.taxonomySection}>
            <h2 className={styles.taxonomyTitle}>📊 Taxonomy Matrix</h2>
            <table className={styles.taxonomyTable}>
                <thead>
                    <tr>
                        <th>Theme</th>
                        {matrix.columns.map((col) => (
                            <th key={col}>{col}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {matrix.themes.map((theme) => (
                        <tr key={theme}>
                            <td style={{ fontWeight: 'var(--font-medium)' }}>{theme}</td>
                            {matrix.columns.map((col) => {
                                const cell = matrix.cells.find(
                                    (c) => c.theme === theme && (c.dataset === col || c.metric === col || c.method === col)
                                );
                                return (
                                    <td key={col}>
                                        {cell?.value || '—'}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function CitationAuditBadge({
    reportId,
}: {
    reportId: string;
}) {
    const { data: audit } = useQuery({
        queryKey: ['citation-audit', reportId],
        queryFn: () =>
            reportService.getCitationAuditStatus(reportId).then((r) => r.data),
    });

    if (!audit) return null;

    const allVerified = audit.uncertain === 0;

    return (
        <div
            className={`${styles.auditBadge} ${allVerified ? styles.verified : styles.uncertain
                }`}
        >
            {allVerified ? (
                <>
                    <CheckCircle size={16} />
                    ✅ {audit.verified}/{audit.total} claims verified
                </>
            ) : (
                <>
                    <AlertTriangle size={16} />
                    ⚠️ {audit.uncertain} claim{audit.uncertain > 1 ? 's' : ''} uncertain
                </>
            )}
        </div>
    );
}

export default function ReportDetailPage() {
    const params = useParams();
    const id = params.id as string;

    const { data: report, isLoading } = useQuery({
        queryKey: ['report', id],
        queryFn: () => reportService.getById(id).then((r) => r.data),
    });

    const { data: taxonomy } = useQuery({
        queryKey: ['taxonomy', id],
        queryFn: () => reportService.getTaxonomyMatrix(id).then((r) => r.data),
        enabled: !!report,
    });

    const { data: claims } = useQuery({
        queryKey: ['claims', id],
        queryFn: () => reportService.getClaims(id).then((r) => r.data),
        enabled: !!report,
    });

    if (isLoading) {
        return (
            <AppShell title="Report">
                <Skeleton variant="heading" width="50%" />
                <Skeleton height={400} />
            </AppShell>
        );
    }

    if (!report) {
        return (
            <AppShell title="Report">
                <p>Report not found</p>
            </AppShell>
        );
    }

    return (
        <AppShell title="Report">
            <Link href="/reports" className={styles.backLink}>
                <ArrowLeft size={16} /> Back to Reports
            </Link>

            <div className={styles.reportContainer}>
                {/* Main content */}
                <div className={styles.reportContent}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {report.content}
                    </ReactMarkdown>

                    {taxonomy && <TaxonomyView matrix={taxonomy} />}
                </div>

                {/* Side panel */}
                <div className={styles.sidePanel}>
                    <Card>
                        <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-md)' }}>
                            Report Info
                        </h3>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                            <div>
                                <FileText size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                                {report.paper_count} papers
                            </div>
                            <div>Created: {formatDate(report.created_at)}</div>
                            {report.topic && <div>Topic: {report.topic}</div>}
                        </div>
                    </Card>

                    <CitationAuditBadge reportId={id} />

                    {/* Key claims */}
                    {claims && claims.length > 0 && (
                        <Card>
                            <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-md)' }}>
                                Key Claims
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                                {claims.slice(0, 5).map((claim) => (
                                    <div key={claim.claim_id} className={styles.citationDetail}>
                                        <div className={styles.citationDetailTitle}>
                                            {claim.uncertainty_flag && '⚠️ '}
                                            {claim.claim_text}
                                        </div>
                                        <div className={styles.citationDetailMeta}>
                                            Salience: {(claim.salience_score * 100).toFixed(0)}% ·{' '}
                                            {claim.evidence_span_ids.length} evidence span
                                            {claim.evidence_span_ids.length !== 1 ? 's' : ''}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    )}
                </div>
            </div>
        </AppShell>
    );
}
