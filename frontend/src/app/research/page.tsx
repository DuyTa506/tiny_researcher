'use client';

import { useState, useRef, useEffect, Suspense, type FormEvent } from 'react';
import { useSearchParams } from 'next/navigation';
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
    pendingApproval: ApprovalGate | null
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
            label: phase.label,
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
}: {
    event: ChatEvent;
    onApprove?: (gateId: string) => void;
    onReject?: (gateId: string) => void;
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
                            Screening Summary
                        </div>
                        <div className={styles.screeningStats}>
                            <div className={styles.stat}>
                                <span className={styles.statValue}>{event.screeningSummary.included}</span>
                                <span className={styles.statLabel}>Included</span>
                            </div>
                            <div className={styles.stat}>
                                <span className={styles.statValue}>{event.screeningSummary.excluded}</span>
                                <span className={styles.statLabel}>Excluded</span>
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
                        Approval Required
                    </div>
                    <div className={styles.approvalContext}>{event.gate.context}</div>
                    {event.gate.estimated_cost && (
                        <div className={styles.approvalCost}>
                            Estimated cost: {event.gate.estimated_cost}
                        </div>
                    )}
                    <div className={styles.approvalActions}>
                        <Button onClick={() => onApprove(event.gate!.gate_id)} size="sm">
                            <CheckCircle size={14} /> Approve
                        </Button>
                        <Button variant="secondary" onClick={() => onReject(event.gate!.gate_id)} size="sm">
                            <SkipForward size={14} /> Skip
                        </Button>
                        <Button variant="ghost" onClick={() => onReject(event.gate!.gate_id)} size="sm">
                            <XCircle size={14} /> Cancel
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
        const text = input.trim();
        if (!text) return;
        setInput('');

        if (!conversationId) {
            await createSession(text);
        }
        sendMessage(text);
    };

    const stepperItems = buildStepperItems(pipelineStatus, pendingApproval);
    const hasStarted = events.length > 0 || isStreaming;

    return (
        <div className={styles.page}>
            {/* Left Sidebar */}
            <aside className={styles.sidebar}>
                <div className={styles.sidebarHeader}>
                    <div className={styles.sidebarTitle}>
                        {conversationId ? 'Research Pipeline' : 'New Research'}
                    </div>
                    <div className={styles.sidebarSub}>
                        {conversationId ? `ID: ${conversationId.slice(0, 8)}…` : 'Start a conversation to begin'}
                    </div>
                    <div className={`${styles.statusBadge} ${conversationState === 'COMPLETE' ? styles.complete : error ? styles.error : ''}`}>
                        <Badge variant={conversationState === 'COMPLETE' ? 'high' : conversationState === 'EXECUTING' ? 'info' : 'medium'}>
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
                    <span className={styles.chatTitle}>Research Chat</span>
                    <div className={styles.chatActions}>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => createSession()}
                        >
                            <Plus size={14} /> New
                        </Button>
                    </div>
                </div>

                {error && (
                    <div className={styles.errorBanner}>
                        <AlertCircle size={14} />
                        {error}
                    </div>
                )}

                {!hasStarted ? (
                    <div className={styles.welcome}>
                        <div className={styles.welcomeIcon}>
                            <Microscope size={28} />
                        </div>
                        <div className={styles.welcomeTitle}>Research Assistant</div>
                        <div className={styles.welcomeDesc}>
                            Describe your research topic. I&apos;ll search papers, screen for relevance,
                            extract evidence, and generate a citation-grounded report — all streamed live.
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
                            />
                        ))}
                        {isStreaming && events.length > 0 && !events[events.length - 1]?.isStreaming && (
                            <div className={styles.typing}>
                                <Bot size={14} />
                                Processing
                                <span className={styles.typingDots}>
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
                            placeholder={conversationId ? 'Type a message…' : 'Describe your research topic…'}
                            rows={1}
                        />
                        <button
                            type="submit"
                            className={styles.sendBtn}
                            disabled={!input.trim()}
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
