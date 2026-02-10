'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { MessageSquare, Trash2, Clock, Plus } from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import Modal from '@/components/ui/Modal';
import { conversationService } from '@/services/conversations';
import { formatDate } from '@/lib/utils';
import styles from './styles.module.css';

const STATE_VARIANT: Record<string, 'high' | 'medium' | 'low' | 'info' | 'none'> = {
    COMPLETE: 'high',
    EXECUTING: 'info',
    REVIEWING: 'medium',
    PLANNING: 'medium',
    CLARIFYING: 'low',
    IDLE: 'none',
};

export default function SessionsPage() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; topic: string } | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ['sessions'],
        queryFn: () => conversationService.list().then((r) => r.data),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => conversationService.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sessions'] });
            setDeleteTarget(null);
        },
    });

    const sessions = (data as Record<string, string>[] | undefined) ?? [];

    return (
        <AppShell title="Sessions">
            <div className={styles.topBar}>
                <span className={styles.count}>
                    {isLoading ? '...' : `${sessions.length} sessions`}
                </span>
                <Button onClick={() => router.push('/research')}>
                    <Plus size={14} /> New Research
                </Button>
            </div>

            {isLoading ? (
                <div className={styles.grid}>
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Card key={i}>
                            <Skeleton variant="heading" />
                            <Skeleton variant="text" />
                            <Skeleton variant="text" width="60%" />
                        </Card>
                    ))}
                </div>
            ) : !sessions.length ? (
                <div className={styles.empty}>
                    <MessageSquare size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
                    <p>No research sessions yet</p>
                    <Button
                        variant="primary"
                        onClick={() => router.push('/research')}
                        style={{ marginTop: 16 }}
                    >
                        Start your first research
                    </Button>
                </div>
            ) : (
                <div className={styles.grid}>
                    {sessions.map((session) => {
                        const id = session.conversation_id || session.id;
                        const state = session.state || 'IDLE';
                        const topic = session.current_topic || session.topic || `Session ${id?.slice(0, 8)}`;

                        return (
                            <Card key={id} hoverable>
                                <div
                                    className={styles.sessionCard}
                                    onClick={() => router.push(`/research?id=${id}`)}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => e.key === 'Enter' && router.push(`/research?id=${id}`)}
                                >
                                    <div className={styles.sessionHeader}>
                                        <h3 className={styles.sessionTitle}>{topic}</h3>
                                        <Badge variant={STATE_VARIANT[state] || 'none'}>
                                            {state}
                                        </Badge>
                                    </div>
                                    <div className={styles.sessionMeta}>
                                        <span>
                                            <MessageSquare size={12} style={{ verticalAlign: 'middle' }} />{' '}
                                            {session.message_count ?? 0} messages
                                        </span>
                                        {session.created_at && (
                                            <span>
                                                <Clock size={12} style={{ verticalAlign: 'middle' }} />{' '}
                                                {formatDate(session.created_at)}
                                            </span>
                                        )}
                                    </div>
                                    <div className={styles.sessionFooter}>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setDeleteTarget({ id, topic });
                                            }}
                                        >
                                            <Trash2 size={14} />
                                        </Button>
                                    </div>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Delete confirmation modal */}
            <Modal
                open={!!deleteTarget}
                onClose={() => setDeleteTarget(null)}
                title="Delete Session"
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
                    Are you sure you want to delete session <strong>{deleteTarget?.topic}</strong>?
                    This action cannot be undone.
                </p>
            </Modal>
        </AppShell>
    );
}
