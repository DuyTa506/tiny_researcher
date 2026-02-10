'use client';

import { useState, useRef, useEffect, Suspense, type FormEvent } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import {
    Send,
    Microscope,
    Bot,
    User,
    Shield,
    CheckCircle,
    XCircle,
    SkipForward,
    Filter,
    AlertCircle,
    Plus,
    ArrowRight,
    Loader,
} from 'lucide-react';
import AppShell from '@/components/layout/AppShell';
import Stepper, { type StepItem } from '@/components/ui/Stepper';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import ThinkingBubble from '@/components/chat/ThinkingBubble';
import StreamingText from '@/components/chat/StreamingText';
import PlanCard from '@/components/chat/PlanCard';
import PapersCollectedCard from '@/components/chat/PapersCollectedCard';
import EvidenceCard from '@/components/chat/EvidenceCard';
import TaxonomyPreview from '@/components/chat/TaxonomyPreview';
import ClaimsCard from '@/components/chat/ClaimsCard';
import ActivityLog from '@/components/chat/ActivityLog';
import { useResearchChat } from '@/hooks/useResearchChat';
import { PIPELINE_PHASES } from '@/lib/constants';
import type { ChatEvent, PipelineStatus, ApprovalGate } from '@/lib/types';
import styles from './styles.module.css';

/* ─── Stepper builder ─── */

function buildStepperItems(
    pipeline: PipelineStatus | null,
    pendingApproval: ApprovalGate | null,
    t: (key: string) => string
): StepItem[] {
    return PIPELINE_PHASES.map((phase, i) => {
        let status: StepItem['status'] = 'pending';
        let detail: string | undefined;
        let progress: number | undefined;
        let total: number | undefined;

        if (pipeline) {
            if (i < pipeline.phase_index) {
                status = 'complete';
            } else if (i === pipeline.phase_index) {
                if (pendingApproval) {
                    status = 'paused';
                    detail = 'Approval required';
                } else {
                    status = 'active';
                    progress = pipeline.progress;
                    total = pipeline.total;
                    detail = pipeline.message;
                }
            }
        }

        return {
            key: phase.key,
            label: t(`pipeline.${phase.key}`),
            status,
            detail,
            progress,
            total,
        };
    });
}

/* ─── ChatEvent renderer ─── */

function ChatEventRenderer({
    event,
    onApprove,
    onReject,
    t,
}: {
    event: ChatEvent;
    onApprove?: (gateId: string) => void;
    onReject?: (gateId: string) => void;
    t: (key: string) => string;
}) {
    switch (event.type) {
        case 'message': {
            const isUser = event.role === 'user';
            const isSystem = event.role === 'system';
            return (
                <div
                    className={`${styles.message} ${isUser ? styles.user : isSystem ? styles.system : ''
                        }`}
                >
                    {!isSystem && (
                        <div className={`${styles.avatar} ${isUser ? styles.user : styles.assistant}`}>
                            {isUser ? <User size={16} /> : <Bot size={16} />}
                        </div>
                    )}
                    <div
                        className={`${styles.bubble} ${isUser ? styles.user : isSystem ? styles.system : styles.assistant
                            }`}
                    >
                        {isUser ? (
                            event.content
                        ) : (
                            <StreamingText
                                content={event.content || ''}
                                isStreaming={!!event.isStreaming}
                            />
                        )}
                    </div>
                </div>
            );
        }

        case 'thinking':
            return event.thinking ? (
                <ThinkingBubble
                    content={event.thinking.content}
                    phase={event.thinking.phase}
                    phaseLabel={PIPELINE_PHASES.find((p) => p.key === event.thinking!.phase)?.label}
                />
            ) : null;

        case 'plan':
            return event.plan ? (
                <div className={styles.inlineCard}>
                    <PlanCard plan={event.plan} />
                </div>
            ) : null;

        case 'screening':
            return event.screeningSummary ? (
                <div className={styles.inlineCard}>
                    <div className={styles.screeningCard}>
                        <div className={styles.screeningHeader}>
                            <Filter size={16} />
                            {t('research.screeningSummary')}
                        </div>
                        <div className={styles.screeningStats}>
                            <div className={styles.stat}>
                                <span className={styles.statValue}>{event.screeningSummary.included}</span>
                                <span className={styles.statLabel}>{t('research.included')}</span>
                            </div>
                            <div className={styles.stat}>
                                <span className={styles.statValue}>{event.screeningSummary.excluded}</span>
                                <span className={styles.statLabel}>{t('research.excluded')}</span>
                            </div>
                        </div>
                        <div className={styles.reasonList}>
                            {Object.entries(event.screeningSummary.reasons)
                                .sort(([, a], [, b]) => b - a)
                                .slice(0, 5)
                                .map(([reason, count]) => (
                                    <span key={reason} className={styles.reasonTag}>
                                        {reason} ({count})
                                    </span>
                                ))}
                        </div>
                    </div>
                </div>
            ) : null;

        case 'papers':
            return event.papers ? (
                <div className={styles.inlineCard}>
                    <PapersCollectedCard papers={event.papers} />
                </div>
            ) : null;

        case 'evidence':
            return event.evidence ? (
                <div className={styles.inlineCard}>
                    <EvidenceCard
                        paperTitle={event.evidence.paper_title}
                        spansCount={event.evidence.spans_count}
                        sampleSnippet={event.evidence.sample_snippet}
                    />
                </div>
            ) : null;

        case 'taxonomy':
            return event.taxonomy ? (
                <div className={styles.inlineCard}>
                    <TaxonomyPreview matrix={event.taxonomy} />
                </div>
            ) : null;

        case 'claims':
            return (
                <div className={styles.inlineCard}>
                    <ClaimsCard claims={event.claims} />
                </div>
            );

        case 'gaps':
            return (
                <div className={styles.inlineCard}>
                    <ClaimsCard gaps={event.gaps} />
                </div>
            );

        case 'state_change':
            return event.stateChange ? (
                <div className={styles.stateChange}>
                    <span>{event.stateChange.from}</span>
                    <ArrowRight size={12} className={styles.stateArrow} />
                    <span>{event.stateChange.to}</span>
                </div>
            ) : null;

        case 'approval':
            return event.gate && onApprove && onReject ? (
                <div className={styles.approvalCard}>
                    <div className={styles.approvalHeader}>
                        <Shield size={20} />
                        {t('research.approvalRequired')}
                    </div>
                    <div className={styles.approvalContext}>{event.gate.context}</div>
                    {event.gate.estimated_cost && (
                        <div className={styles.approvalCost}>
                            {t('research.estimatedCost')}: {event.gate.estimated_cost}
                        </div>
                    )}
                    <div className={styles.approvalActions}>
                        <Button onClick={() => onApprove(event.gate!.gate_id)} size="sm">
                            <CheckCircle size={14} /> {t('research.approve')}
                        </Button>
                        <Button variant="secondary" onClick={() => onReject(event.gate!.gate_id)} size="sm">
                            <SkipForward size={14} /> {t('research.skip')}
                        </Button>
                        <Button variant="ghost" onClick={() => onReject(event.gate!.gate_id)} size="sm">
                            <XCircle size={14} /> {t('research.cancel')}
                        </Button>
                    </div>
                </div>
            ) : null;

        default:
            return null;
    }
}

/* ─── Inner Research Content (uses useSearchParams) ─── */

function ResearchContent() {
    const searchParams = useSearchParams();
    const initialId = searchParams.get('id');
    const { t, i18n } = useTranslation();

    const {
        events,
        sendMessage,
        pipelineStatus,
        conversationState,
        pendingApproval,
        approveGate,
        rejectGate,
        activityLog,
        isStreaming,
        error,
        createSession,
        conversationId,
    } = useResearchChat(initialId);

    const [input, setInput] = useState('');
    const timelineEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        timelineEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [events.length]);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        let text = input.trim();
        if (!text) return;
        setInput('');

        // Inject language instruction if Vietnamese (only for backend, not displayed)
        let sendText = text;
        if (i18n.language === 'vi') {
            sendText += ' (Please conduct this research, write the report, and respond in Vietnamese)';
        }

        if (!conversationId) {
            const newId = await createSession(text);
            sendMessage(sendText, newId);
        } else {
            sendMessage(sendText);
        }
    };

    const stepperItems = buildStepperItems(pipelineStatus, pendingApproval, t);
    const hasStarted = events.length > 0 || isStreaming;

    return (
        <div className={styles.page}>
            {/* Left Sidebar */}
            <aside className={styles.sidebar}>
                <div className={styles.sidebarHeader}>
                    <div className={styles.sidebarTitle}>
                        {conversationId ? t('research.pipeline') : t('research.newResearch')}
                    </div>
                    <div className={styles.sidebarSub}>
                        {conversationId ? `ID: ${conversationId.slice(0, 8)}…` : t('research.startConversation')}
                    </div>
                    <div className={`${styles.statusBadge} ${conversationState === 'COMPLETE' ? styles.complete : error ? styles.error : isStreaming ? styles.active : ''}`}>
                        <Badge variant={conversationState === 'COMPLETE' ? 'high' : conversationState === 'EXECUTING' ? 'info' : isStreaming ? 'info' : 'medium'}>
                            {conversationState}
                        </Badge>
                    </div>
                </div>

                {/* Pipeline Stepper */}
                <div className={styles.stepperWrap}>
                    <Stepper steps={stepperItems} />
                </div>

                {/* Activity Log */}
                <div className={styles.activityWrap}>
                    <ActivityLog entries={activityLog} />
                </div>
            </aside>

            {/* Chat Area */}
            <div className={styles.chatArea}>
                <div className={styles.chatHeader}>
                    <Microscope size={20} />
                    <span className={styles.chatTitle}>{t('research.chatTitle')}</span>
                    <div className={styles.chatActions}>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => createSession()}
                        >
                            <Plus size={14} /> {t('research.new')}
                        </Button>
                    </div>
                </div>

                {error && (
                    <div className={styles.errorBanner} role="alert" aria-live="assertive">
                        <AlertCircle size={14} />
                        {error}
                    </div>
                )}

                {!hasStarted ? (
                    <div className={styles.welcome}>
                        <div className={styles.welcomeIcon}>
                            <Microscope size={28} />
                        </div>
                        <div className={styles.welcomeTitle}>{t('research.welcomeTitle')}</div>
                        <div className={styles.welcomeDesc}>
                            {t('research.welcomeDesc')}
                        </div>
                    </div>
                ) : (
                    <div className={styles.timeline}>
                        {events.map((evt) => (
                            <ChatEventRenderer
                                key={evt.id}
                                event={evt}
                                onApprove={approveGate}
                                onReject={rejectGate}
                                t={t}
                            />
                        ))}
                        {isStreaming && events.length > 0 && !events[events.length - 1]?.isStreaming && (
                            <div className={styles.processing}>
                                <div className={styles.processingIcon}>
                                    <Loader size={16} />
                                </div>
                                <div className={styles.processingText}>
                                    <span className={styles.processingLabel}>
                                        {t('research.processing')}
                                    </span>
                                    <span className={styles.processingState}>
                                        {conversationState}
                                    </span>
                                </div>
                                <span className={styles.processingDots}>
                                    <span /><span /><span />
                                </span>
                            </div>
                        )}
                        <div ref={timelineEndRef} />
                    </div>
                )}

                {/* Input */}
                <div className={styles.inputArea}>
                    <form className={styles.inputForm} onSubmit={handleSubmit}>
                        <textarea
                            className={styles.inputField}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSubmit(e);
                                }
                            }}
                            placeholder={conversationId ? t('research.typePlaceholder') : t('research.topicPlaceholder')}
                            rows={1}
                            aria-label={conversationId ? 'Type your message' : 'Enter research topic'}
                        />
                        <button
                            type="submit"
                            className={styles.sendBtn}
                            disabled={!input.trim()}
                            aria-label="Send message"
                        >
                            <Send size={16} />
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}

/* ─── Page wrapper with Suspense ─── */

export default function ResearchPage() {
    return (
        <AppShell title="Research">
            <Suspense fallback={<div>Loading…</div>}>
                <ResearchContent />
            </Suspense>
        </AppShell>
    );
}
