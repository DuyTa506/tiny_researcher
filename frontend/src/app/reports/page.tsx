'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { BookOpen, FileText, Clock, Trash2, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import Modal from '@/components/ui/Modal';
import { reportService } from '@/services/reports';
import { formatDate, truncate } from '@/lib/utils';
import styles from './styles.module.css';

export default function ReportsListPage() {
    const queryClient = useQueryClient();
    const [keyword, setKeyword] = useState('');
    const [page, setPage] = useState(1);
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ['reports', { keyword, page }],
        queryFn: () =>
            reportService
                .list({
                    keyword: keyword || undefined,
                    page,
                    page_size: 20,
                })
                .then((r) => r.data),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => reportService.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
            setDeleteTarget(null);
        },
    });

    const handleExport = async (id: string, title: string, format: 'markdown' | 'html') => {
        const response = await reportService.export(id, format);
        const blob = new Blob([response.data], {
            type: format === 'html' ? 'text/html' : 'text/markdown',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title}.${format === 'html' ? 'html' : 'md'}`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const reports = data?.items ?? [];
    const totalPages = data?.total_pages ?? 1;
    const total = data?.total ?? 0;

    return (
        <AppShell title="Reports">
            <div style={{ maxWidth: 900, marginBottom: 'var(--space-lg)' }}>
                <Input
                    placeholder="Search reports..."
                    value={keyword}
                    onChange={(e) => {
                        setKeyword(e.target.value);
                        setPage(1);
                    }}
                />
            </div>

            <div style={{ marginBottom: 'var(--space-md)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                {isLoading ? '...' : `${total} reports`}
            </div>

            {isLoading ? (
                <div className={styles.grid}>
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Card key={i}>
                            <Skeleton variant="heading" />
                            <Skeleton variant="text" />
                            <Skeleton variant="text" width="60%" />
                        </Card>
                    ))}
                </div>
            ) : !reports.length ? (
                <div className={styles.empty}>
                    <BookOpen size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
                    <p>No reports generated yet</p>
                </div>
            ) : (
                <>
                    <div className={styles.grid}>
                        {reports.map((report) => (
                            <Card key={report._id ?? report.id} hoverable>
                                <div className={styles.reportCard}>
                                    <Link
                                        href={`/reports/${report._id ?? report.id}`}
                                        style={{ textDecoration: 'none' }}
                                    >
                                        <h3 className={styles.reportTitle}>
                                            {report.title || report.topic || `Report #${(report._id ?? report.id ?? '').slice(0, 8)}`}
                                        </h3>
                                    </Link>
                                    <div className={styles.reportMeta}>
                                        {report.paper_count != null && (
                                            <span>
                                                <FileText size={12} style={{ verticalAlign: 'middle' }} />{' '}
                                                {report.paper_count} papers
                                            </span>
                                        )}
                                        <span>
                                            <Clock size={12} style={{ verticalAlign: 'middle' }} />{' '}
                                            {formatDate(report.created_at)}
                                        </span>
                                    </div>
                                    {report.content && (
                                        <p className={styles.reportPreview}>
                                            {truncate(report.content.replace(/[#*_]/g, ''), 200)}
                                        </p>
                                    )}
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto' }}>
                                        <Badge variant="high" dot>
                                            Complete
                                        </Badge>
                                        <div style={{ display: 'flex', gap: 4 }}>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() =>
                                                    handleExport(
                                                        report._id ?? report.id ?? '',
                                                        report.title || report.topic || 'report',
                                                        'markdown'
                                                    )
                                                }
                                            >
                                                <Download size={14} />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() =>
                                                    setDeleteTarget({
                                                        id: report._id ?? report.id ?? '',
                                                        title: report.title || report.topic || 'this report',
                                                    })
                                                }
                                            >
                                                <Trash2 size={14} />
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </Card>
                        ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-md)', marginTop: 'var(--space-xl)' }}>
                            <Button
                                variant="ghost"
                                size="sm"
                                disabled={page <= 1}
                                onClick={() => setPage((p) => p - 1)}
                            >
                                <ChevronLeft size={16} />
                            </Button>
                            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
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
                </>
            )}

            {/* Delete confirmation modal */}
            <Modal
                open={!!deleteTarget}
                onClose={() => setDeleteTarget(null)}
                title="Delete Report"
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
