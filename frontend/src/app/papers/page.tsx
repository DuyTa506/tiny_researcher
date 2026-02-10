'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { FileText, ExternalLink, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import Modal from '@/components/ui/Modal';
import { paperService } from '@/services/papers';
import { getScoreColor, truncate, formatDate } from '@/lib/utils';
import type { PaperStatus } from '@/lib/types';
import styles from './styles.module.css';

const STATUS_OPTIONS: PaperStatus[] = [
    'RAW',
    'SCREENED',
    'FULLTEXT',
    'EXTRACTED',
    'REPORTED',
];

const SOURCE_OPTIONS = ['arxiv', 'openalex', 'huggingface', 'url', 'manual'];

export default function PapersPage() {
    const queryClient = useQueryClient();
    const [status, setStatus] = useState<string>('');
    const [source, setSource] = useState<string>('');
    const [keyword, setKeyword] = useState<string>('');
    const [page, setPage] = useState(1);
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ['papers', { status, source, keyword, page }],
        queryFn: () =>
            paperService
                .list({
                    status: status || undefined,
                    source: source || undefined,
                    keyword: keyword || undefined,
                    page,
                    page_size: 20,
                })
                .then((r) => r.data),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => paperService.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['papers'] });
            setDeleteTarget(null);
        },
    });

    const clearFilters = () => {
        setStatus('');
        setSource('');
        setKeyword('');
        setPage(1);
    };

    const hasFilters = status || source || keyword;
    const papers = data?.items ?? [];
    const totalPages = data?.total_pages ?? 1;
    const total = data?.total ?? 0;

    return (
        <AppShell title="Papers">
            <div className={styles.wrapper}>
                {/* Filter sidebar */}
                <div className={styles.filters}>
                    <Card>
                        <Input
                            placeholder="Search papers..."
                            value={keyword}
                            onChange={(e) => {
                                setKeyword(e.target.value);
                                setPage(1);
                            }}
                        />

                        <div className={styles.filterGroup} style={{ marginTop: 'var(--space-md)' }}>
                            <label htmlFor="status-filter">Status</label>
                            <select id="status-filter" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                                <option value="">All Status</option>
                                {STATUS_OPTIONS.map((s) => (
                                    <option key={s} value={s}>
                                        {s}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className={styles.filterGroup} style={{ marginTop: 'var(--space-md)' }}>
                            <label htmlFor="source-filter">Source</label>
                            <select id="source-filter" value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }}>
                                <option value="">All Sources</option>
                                {SOURCE_OPTIONS.map((s) => (
                                    <option key={s} value={s}>
                                        {s}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {hasFilters && (
                            <button className={styles.clearBtn} onClick={clearFilters}>
                                Clear all filters
                            </button>
                        )}
                    </Card>
                </div>

                {/* Paper list */}
                <div>
                    <div className={styles.topBar}>
                        <span className={styles.resultCount}>
                            {isLoading ? '...' : `${total} papers`}
                        </span>
                    </div>

                    <div className={styles.paperGrid}>
                        {isLoading ? (
                            Array.from({ length: 6 }).map((_, i) => (
                                <Card key={i}>
                                    <Skeleton variant="heading" />
                                    <Skeleton variant="text" />
                                    <Skeleton variant="text" width="80%" />
                                </Card>
                            ))
                        ) : !papers.length ? (
                            <div className={styles.empty}>
                                <FileText size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
                                <p>No papers found</p>
                            </div>
                        ) : (
                            papers.map((paper) => (
                                <Card key={paper._id ?? paper.id ?? paper.title} hoverable>
                                    <div className={styles.paperCard}>
                                        <div className={styles.paperHeader}>
                                            <Link
                                                href={`/papers/${paper._id ?? paper.id}`}
                                                style={{ textDecoration: 'none', flex: 1 }}
                                            >
                                                <h3 className={styles.paperTitle}>{paper.title}</h3>
                                            </Link>
                                            {paper.relevance_score != null && (
                                                <div
                                                    className={`${styles.scoreCircle} ${styles[getScoreColor(paper.relevance_score)]}`}
                                                >
                                                    {paper.relevance_score.toFixed(1)}
                                                </div>
                                            )}
                                        </div>

                                        <div className={styles.paperMeta}>
                                            <span>
                                                {paper.authors?.slice(0, 2).join(', ')}
                                                {paper.authors?.length > 2 && ' et al.'}
                                            </span>
                                            {paper.published_date && (
                                                <>
                                                    <span>·</span>
                                                    <span>{formatDate(paper.published_date)}</span>
                                                </>
                                            )}
                                        </div>

                                        <p className={styles.paperAbstract}>
                                            {truncate(paper.abstract, 200)}
                                        </p>

                                        <div className={styles.paperFooter}>
                                            <div className={styles.paperTags}>
                                                <Badge variant="info">{paper.source}</Badge>
                                                <Badge>{paper.status}</Badge>
                                            </div>
                                            <div style={{ display: 'flex', gap: 4 }}>
                                                {paper.url && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            window.open(paper.url, '_blank');
                                                        }}
                                                        aria-label="Open paper source in new tab"
                                                    >
                                                        <ExternalLink size={14} />
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() =>
                                                        setDeleteTarget({
                                                            id: paper._id ?? paper.id ?? '',
                                                            title: paper.title,
                                                        })
                                                    }
                                                    aria-label={`Delete paper: ${paper.title}`}
                                                >
                                                    <Trash2 size={14} />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                </Card>
                            ))
                        )}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className={styles.pagination}>
                            <Button
                                variant="ghost"
                                size="sm"
                                disabled={page <= 1}
                                onClick={() => setPage((p) => p - 1)}
                            >
                                <ChevronLeft size={16} />
                            </Button>
                            <span className={styles.pageInfo}>
                                Page {page} of {totalPages}
                            </span>
                            <Button
                                variant="ghost"
                                size="sm"
                                disabled={page >= totalPages}
                                onClick={() => setPage((p) => p + 1)}
                            >
                                <ChevronRight size={16} />
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            {/* Delete confirmation modal */}
            <Modal
                open={!!deleteTarget}
                onClose={() => setDeleteTarget(null)}
                title="Delete Paper"
                footer={
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
                            Cancel
                        </Button>
                        <Button
                            variant="danger"
                            loading={deleteMutation.isPending}
                            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
                        >
                            Delete
                        </Button>
                    </div>
                }
            >
                <p>
                    Are you sure you want to delete <strong>{deleteTarget?.title}</strong>? This
                    action cannot be undone.
                </p>
            </Modal>
        </AppShell>
    );
}
