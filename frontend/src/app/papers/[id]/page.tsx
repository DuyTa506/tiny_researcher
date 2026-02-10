'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
    ArrowLeft,
    ExternalLink,
    BookOpen,
    CheckCircle,
    XCircle,
    Paperclip,
} from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import { paperService } from '@/services/papers';
import { getScoreColor, formatDate } from '@/lib/utils';
import type { EvidenceSpan } from '@/lib/types';
import styles from './styles.module.css';

function EvidencePopover({
    span,
    onClose,
    anchorRef,
}: {
    span: EvidenceSpan;
    onClose: () => void;
    anchorRef: HTMLElement | null;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const [pos, setPos] = useState({ top: 0, left: 0 });

    useEffect(() => {
        if (anchorRef) {
            const rect = anchorRef.getBoundingClientRect();
            setPos({
                top: rect.bottom + 8,
                left: Math.min(rect.left, window.innerWidth - 400),
            });
        }
    }, [anchorRef]);

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                onClose();
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [onClose]);

    return (
        <div ref={ref} className={styles.popover} style={pos}>
            <div className={styles.popoverSnippet}>&ldquo;{span.snippet}&rdquo;</div>
            <div className={styles.popoverMeta}>
                {span.locator.page && <span>Page {span.locator.page}</span>}
                {span.locator.section && <span>§ {span.locator.section}</span>}
                <span>Confidence: {(span.confidence * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}

function EvidenceButton({
    span,
}: {
    span: EvidenceSpan;
}) {
    const [showPopover, setShowPopover] = useState(false);
    const btnRef = useRef<HTMLButtonElement>(null);

    const handleClose = useCallback(() => {
        setShowPopover(false);
    }, []);

    return (
        <>
            <button
                ref={btnRef}
                className={styles.evidenceLink}
                onClick={() => setShowPopover(!showPopover)}
                aria-label="View evidence"
            >
                <Paperclip size={12} />
            </button>
            {showPopover && (
                <EvidencePopover
                    span={span}
                    onClose={handleClose}
                    anchorRef={btnRef.current}
                />
            )}
        </>
    );
}

export default function PaperDetailPage() {
    const params = useParams();
    const id = params.id as string;

    const { data: paper, isLoading: paperLoading } = useQuery({
        queryKey: ['paper', id],
        queryFn: () => paperService.getById(id).then((r) => r.data),
    });

    const { data: studyCard } = useQuery({
        queryKey: ['study-card', id],
        queryFn: () => paperService.getStudyCard(id).then((r) => r.data),
        enabled: !!paper && paper.status !== 'RAW',
    });

    const { data: screening } = useQuery({
        queryKey: ['screening', id],
        queryFn: () => paperService.getScreeningRecord(id).then((r) => r.data),
        enabled: !!paper && paper.status !== 'RAW',
    });

    const { data: evidenceSpans } = useQuery({
        queryKey: ['evidence-spans', id],
        queryFn: () => paperService.getEvidenceSpans(id).then((r) => r.data),
        enabled: !!studyCard,
    });

    const getSpansForField = (field: string) =>
        evidenceSpans?.filter((s) => s.field === field) ?? [];

    if (paperLoading) {
        return (
            <AppShell title="Paper">
                <div className={styles.container}>
                    <Skeleton variant="heading" width="60%" />
                    <Skeleton variant="text" />
                    <Skeleton variant="text" />
                    <Skeleton height={200} />
                </div>
            </AppShell>
        );
    }

    if (!paper) {
        return (
            <AppShell title="Paper">
                <div className={styles.container}>
                    <p>Paper not found</p>
                </div>
            </AppShell>
        );
    }

    return (
        <AppShell title="Paper Detail">
            <div className={styles.container}>
                <Link href="/papers" className={styles.backLink}>
                    <ArrowLeft size={16} /> Back to Papers
                </Link>

                {/* Title + Score */}
                <div className={styles.titleRow}>
                    <h1 className={styles.title}>{paper.title}</h1>
                    {paper.relevance_score != null && (
                        <div
                            className={`${styles.scoreCircle} ${styles[getScoreColor(paper.relevance_score)]
                                }`}
                            style={{ width: 48, height: 48, fontSize: 'var(--text-sm)' }}
                        >
                            {paper.relevance_score.toFixed(1)}
                        </div>
                    )}
                </div>

                {/* Meta */}
                <div className={styles.meta}>
                    <span>{paper.authors.join(', ')}</span>
                    <span>·</span>
                    <span>{formatDate(paper.published_date)}</span>
                </div>

                <div className={styles.tags}>
                    <Badge variant="info">{paper.source}</Badge>
                    <Badge>{paper.status}</Badge>
                    {paper.url && (
                        <a href={paper.url} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="sm">
                                <ExternalLink size={14} /> Open Source
                            </Button>
                        </a>
                    )}
                </div>

                {/* Abstract */}
                <div className={styles.section}>
                    <h2 className={styles.sectionTitle}>
                        <BookOpen size={20} /> Abstract
                    </h2>
                    <p className={styles.abstract}>{paper.abstract}</p>
                </div>

                {/* Study Card */}
                {studyCard && (
                    <div className={styles.section}>
                        <h2 className={styles.sectionTitle}>📋 Study Card</h2>
                        <div className={styles.studyGrid}>
                            {[
                                { label: 'Problem', value: studyCard.problem, field: 'problem' },
                                { label: 'Method', value: studyCard.method, field: 'method' },
                                {
                                    label: 'Datasets',
                                    value: studyCard.datasets.join(', '),
                                    field: 'dataset',
                                },
                                {
                                    label: 'Metrics',
                                    value: studyCard.metrics.join(', '),
                                    field: 'metric',
                                },
                                {
                                    label: 'Results',
                                    value: studyCard.results.join('; '),
                                    field: 'result',
                                },
                                {
                                    label: 'Limitations',
                                    value: studyCard.limitations.join('; '),
                                    field: 'limitation',
                                },
                            ].map((row) => (
                                <>
                                    <div key={`${row.field}-label`} className={styles.studyLabel}>
                                        {row.label}
                                    </div>
                                    <div key={`${row.field}-value`} className={styles.studyValue}>
                                        {row.value}
                                        {getSpansForField(row.field).map((span) => (
                                            <EvidenceButton key={span.span_id} span={span} />
                                        ))}
                                    </div>
                                </>
                            ))}
                        </div>
                    </div>
                )}

                {/* Screening Decision */}
                {screening && (
                    <div className={styles.section}>
                        <h2 className={styles.sectionTitle}>🔍 Screening Decision</h2>
                        <Card>
                            <div className={styles.screeningCard}>
                                <div
                                    className={`${styles.screeningIcon} ${screening.include ? styles.included : styles.excluded
                                        }`}
                                >
                                    {screening.include ? (
                                        <CheckCircle size={20} />
                                    ) : (
                                        <XCircle size={20} />
                                    )}
                                </div>
                                <div className={styles.screeningContent}>
                                    <div className={styles.screeningDecision}>
                                        {screening.include ? 'Included' : 'Excluded'}
                                    </div>
                                    <div className={styles.screeningReason}>
                                        Reason: {screening.reason_code}
                                    </div>
                                    {screening.rationale_short && (
                                        <div className={styles.screeningRationale}>
                                            &ldquo;{screening.rationale_short}&rdquo;
                                        </div>
                                    )}
                                </div>
                            </div>
                        </Card>
                    </div>
                )}
            </div>
        </AppShell>
    );
}
