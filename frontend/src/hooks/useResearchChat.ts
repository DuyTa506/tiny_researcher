'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { conversationService } from '@/services/conversations';
import { generateId } from '@/lib/utils';
import type {
    ChatEvent,
    PipelineStatus,
    ConversationState,
    ApprovalGate,
    ScreeningSummary,
    SSEEvent,
    ResearchPlan,
    PaperBrief,
    TaxonomyMatrix,
    Claim,
    FutureDirection,
    ActivityEntry,
} from '@/lib/types';

export interface UseResearchChatReturn {
    events: ChatEvent[];
    sendMessage: (text: string) => void;
    pipelineStatus: PipelineStatus | null;
    conversationState: ConversationState;
    pendingApproval: ApprovalGate | null;
    approveGate: (gateId: string) => void;
    rejectGate: (gateId: string) => void;
    screeningSummary: ScreeningSummary | null;
    researchPlan: ResearchPlan | null;
    collectedPapers: PaperBrief[];
    taxonomy: TaxonomyMatrix | null;
    claims: Claim[];
    gaps: FutureDirection[];
    activityLog: ActivityEntry[];
    isStreaming: boolean;
    streamingContent: string;
    error: string | null;
    createSession: (topic?: string) => Promise<string>;
    conversationId: string | null;
}

export function useResearchChat(
    initialConversationId?: string | null
): UseResearchChatReturn {
    const [conversationId, setConversationId] = useState<string | null>(
        initialConversationId ?? null
    );
    const [events, setEvents] = useState<ChatEvent[]>([]);
    const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
    const [conversationState, setConversationState] = useState<ConversationState>('IDLE');
    const [pendingApproval, setPendingApproval] = useState<ApprovalGate | null>(null);
    const [screeningSummary, setScreeningSummary] = useState<ScreeningSummary | null>(null);
    const [researchPlan, setResearchPlan] = useState<ResearchPlan | null>(null);
    const [collectedPapers, setCollectedPapers] = useState<PaperBrief[]>([]);
    const [taxonomy, setTaxonomy] = useState<TaxonomyMatrix | null>(null);
    const [claims, setClaims] = useState<Claim[]>([]);
    const [gaps, setGaps] = useState<FutureDirection[]>([]);
    const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState('');
    const [error, setError] = useState<string | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);
    const streamingMessageIdRef = useRef<string | null>(null);

    // Add activity log entry
    const logActivity = useCallback((icon: string, text: string, phase?: string) => {
        setActivityLog((prev) => [
            ...prev,
            {
                id: generateId(),
                timestamp: new Date().toISOString(),
                phase: phase as ActivityEntry['phase'],
                icon,
                text,
            },
        ]);
    }, []);

    // Push a chat event to the timeline
    const pushEvent = useCallback((event: ChatEvent) => {
        setEvents((prev) => [...prev, event]);
    }, []);

    // Connect to SSE stream
    const connectSSE = useCallback((convId: string) => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        const url = conversationService.streamUrl(convId);
        const es = new EventSource(url);
        eventSourceRef.current = es;
        setIsStreaming(true);
        setError(null);

        es.onmessage = (event) => {
            try {
                const data: SSEEvent = JSON.parse(event.data);

                switch (data.type) {
                    case 'progress':
                        setPipelineStatus({
                            phase: data.phase,
                            phase_index: data.phase_index,
                            progress: data.progress,
                            total: data.total,
                            message: data.message,
                        });
                        if (data.message) {
                            logActivity('⏳', data.message, data.phase);
                        }
                        break;

                    case 'state_change':
                        setConversationState(data.to);
                        pushEvent({
                            id: generateId(),
                            type: 'state_change',
                            timestamp: new Date().toISOString(),
                            stateChange: { from: data.from, to: data.to },
                        });
                        logActivity('🔄', `${data.from} → ${data.to}`);
                        break;

                    case 'message':
                        pushEvent({
                            id: generateId(),
                            type: 'message',
                            timestamp: new Date().toISOString(),
                            role: data.role,
                            content: data.content,
                        });
                        logActivity(data.role === 'assistant' ? '🤖' : '📢', data.content.slice(0, 60));
                        break;

                    case 'thinking':
                        pushEvent({
                            id: generateId(),
                            type: 'thinking',
                            timestamp: new Date().toISOString(),
                            thinking: { content: data.content, phase: data.phase },
                        });
                        logActivity('🧠', `Thinking: ${data.content.slice(0, 50)}...`, data.phase);
                        break;

                    case 'token_stream': {
                        if (data.done) {
                            // Finalize: convert streaming message to a complete message
                            if (streamingMessageIdRef.current) {
                                setEvents((prev) =>
                                    prev.map((e) =>
                                        e.id === streamingMessageIdRef.current
                                            ? { ...e, isStreaming: false }
                                            : e
                                    )
                                );
                            }
                            streamingMessageIdRef.current = null;
                            setStreamingContent('');
                        } else {
                            if (!streamingMessageIdRef.current) {
                                // Start new streaming message
                                const id = data.message_id || generateId();
                                streamingMessageIdRef.current = id;
                                pushEvent({
                                    id,
                                    type: 'message',
                                    timestamp: new Date().toISOString(),
                                    role: 'assistant',
                                    content: data.token,
                                    isStreaming: true,
                                });
                                setStreamingContent(data.token);
                            } else {
                                // Append token to existing streaming message
                                setStreamingContent((prev) => prev + data.token);
                                setEvents((prev) =>
                                    prev.map((e) =>
                                        e.id === streamingMessageIdRef.current
                                            ? { ...e, content: (e.content || '') + data.token }
                                            : e
                                    )
                                );
                            }
                        }
                        break;
                    }

                    case 'plan':
                        setResearchPlan(data.plan);
                        pushEvent({
                            id: generateId(),
                            type: 'plan',
                            timestamp: new Date().toISOString(),
                            plan: data.plan,
                        });
                        logActivity('📋', `Plan: ${data.plan.steps.length} steps (${data.plan.mode || 'FULL'})`, 'plan');
                        break;

                    case 'screening_summary':
                        setScreeningSummary(data.summary);
                        pushEvent({
                            id: generateId(),
                            type: 'screening',
                            timestamp: new Date().toISOString(),
                            screeningSummary: data.summary,
                        });
                        logActivity('🔍', `Screening: ${data.summary.included} included, ${data.summary.excluded} excluded`, 'screening');
                        break;

                    case 'papers_collected':
                        setCollectedPapers((prev) => [...prev, ...data.papers]);
                        pushEvent({
                            id: generateId(),
                            type: 'papers',
                            timestamp: new Date().toISOString(),
                            papers: data.papers,
                            content: `${data.count} papers collected`,
                        });
                        logActivity('📄', `Collected ${data.count} papers`, 'collect');
                        break;

                    case 'evidence':
                        pushEvent({
                            id: generateId(),
                            type: 'evidence',
                            timestamp: new Date().toISOString(),
                            evidence: {
                                paper_title: data.paper_title,
                                spans_count: data.spans_count,
                                sample_snippet: data.sample_snippet,
                            },
                        });
                        logActivity('🔬', `Evidence: ${data.spans_count} spans from "${data.paper_title.slice(0, 40)}"`, 'evidence_extraction');
                        break;

                    case 'taxonomy':
                        setTaxonomy(data.matrix);
                        pushEvent({
                            id: generateId(),
                            type: 'taxonomy',
                            timestamp: new Date().toISOString(),
                            taxonomy: data.matrix,
                        });
                        logActivity('📊', `Taxonomy: ${data.matrix.themes.length} themes × ${data.matrix.columns.length} columns`, 'taxonomy');
                        break;

                    case 'claims':
                        setClaims(data.claims);
                        pushEvent({
                            id: generateId(),
                            type: 'claims',
                            timestamp: new Date().toISOString(),
                            claims: data.claims,
                        });
                        logActivity('💡', `${data.claims.length} claims generated`, 'claims_gaps');
                        break;

                    case 'gap_mining':
                        setGaps(data.gaps);
                        pushEvent({
                            id: generateId(),
                            type: 'gaps',
                            timestamp: new Date().toISOString(),
                            gaps: data.gaps,
                        });
                        logActivity('🔮', `${data.gaps.length} future directions identified`, 'claims_gaps');
                        break;

                    case 'approval_required':
                        setPendingApproval(data.gate);
                        pushEvent({
                            id: generateId(),
                            type: 'approval',
                            timestamp: new Date().toISOString(),
                            gate: data.gate,
                        });
                        logActivity('🛡️', `Approval required: ${data.gate.context.slice(0, 50)}`, 'hitl_gate');
                        break;

                    case 'complete':
                        setIsStreaming(false);
                        setConversationState('COMPLETE');
                        logActivity('✅', 'Research complete');
                        es.close();
                        break;

                    case 'error':
                        setError(data.message);
                        setIsStreaming(false);
                        logActivity('❌', data.message);
                        es.close();
                        break;
                }
            } catch {
                console.error('Failed to parse SSE event');
            }
        };

        es.onerror = () => {
            setIsStreaming(false);
            es.close();
        };
    }, [logActivity, pushEvent]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            eventSourceRef.current?.close();
        };
    }, []);

    // Connect when conversationId changes
    useEffect(() => {
        if (conversationId) {
            connectSSE(conversationId);
        }
        return () => {
            eventSourceRef.current?.close();
        };
    }, [conversationId, connectSSE]);

    // Send message
    const sendMessage = useCallback(
        async (text: string) => {
            if (!conversationId) return;

            pushEvent({
                id: generateId(),
                type: 'message',
                timestamp: new Date().toISOString(),
                role: 'user',
                content: text,
            });

            try {
                await conversationService.sendMessage(conversationId, text);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to send message');
            }
        },
        [conversationId, pushEvent]
    );

    // Create session
    const createSession = useCallback(async (topic?: string): Promise<string> => {
        try {
            const res = await conversationService.create(topic);
            const id = res.data.id;
            setConversationId(id);
            setEvents([]);
            setPipelineStatus(null);
            setConversationState('IDLE');
            setPendingApproval(null);
            setScreeningSummary(null);
            setResearchPlan(null);
            setCollectedPapers([]);
            setTaxonomy(null);
            setClaims([]);
            setGaps([]);
            setActivityLog([]);
            setStreamingContent('');
            setError(null);
            return id;
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Failed to create session';
            setError(msg);
            throw err;
        }
    }, []);

    // Approve gate
    const approveGate = useCallback(
        async (gateId: string) => {
            if (!conversationId) return;
            try {
                await conversationService.approveGate(conversationId, gateId);
                setPendingApproval(null);
                logActivity('✅', 'Gate approved');
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to approve gate');
            }
        },
        [conversationId, logActivity]
    );

    // Reject gate
    const rejectGate = useCallback(
        async (gateId: string) => {
            if (!conversationId) return;
            try {
                await conversationService.rejectGate(conversationId, gateId);
                setPendingApproval(null);
                logActivity('⛔', 'Gate rejected');
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to reject gate');
            }
        },
        [conversationId, logActivity]
    );

    return {
        events,
        sendMessage,
        pipelineStatus,
        conversationState,
        pendingApproval,
        approveGate,
        rejectGate,
        screeningSummary,
        researchPlan,
        collectedPapers,
        taxonomy,
        claims,
        gaps,
        activityLog,
        isStreaming,
        streamingContent,
        error,
        createSession,
        conversationId,
    };
}
