'use client';

import { Microscope } from 'lucide-react';
import styles from './styles.module.css';

interface EvidenceCardProps {
    paperTitle: string;
    spansCount: number;
    sampleSnippet?: string;
}

export default function EvidenceCard({ paperTitle, spansCount, sampleSnippet }: EvidenceCardProps) {
    return (
        <div className={styles.card}>
            <div className={styles.header}>
                <Microscope size={16} />
                Evidence Extracted
                <span className={styles.spanCount}>{spansCount} spans</span>
            </div>
            <div className={styles.paperTitle}>{paperTitle}</div>
            {sampleSnippet && (
                <div className={styles.snippet}>&ldquo;{sampleSnippet}&rdquo;</div>
            )}
        </div>
    );
}
