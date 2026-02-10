'use client';

import { useState } from 'react';
import { Brain, ChevronDown, ChevronUp } from 'lucide-react';
import type { PipelinePhase } from '@/lib/types';
import styles from './styles.module.css';

interface ThinkingBubbleProps {
    content: string;
    phase: PipelinePhase;
    phaseLabel?: string;
}

export default function ThinkingBubble({ content, phase, phaseLabel }: ThinkingBubbleProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className={styles.container}>
            <div className={styles.iconWrap}>
                <Brain size={16} />
            </div>
            <div className={styles.body}>
                <div className={styles.header}>
                    <span className={styles.label}>
                        Thinking
                        <span className={styles.dots}>
                            <span /><span /><span />
                        </span>
                    </span>
                    <span className={styles.phase}>{phaseLabel || phase}</span>
                    <button
                        className={styles.toggle}
                        onClick={() => setExpanded(!expanded)}
                        aria-label={expanded ? 'Collapse' : 'Expand'}
                    >
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                </div>
                <div className={`${styles.content} ${expanded ? styles.expanded : styles.collapsed}`}>
                    {content}
                </div>
            </div>
        </div>
    );
}
