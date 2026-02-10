'use client';

import { FileText } from 'lucide-react';
import type { PaperBrief } from '@/lib/types';
import styles from './styles.module.css';

interface PapersCollectedCardProps {
    papers: PaperBrief[];
}

export default function PapersCollectedCard({ papers }: PapersCollectedCardProps) {
    return (
        <div className={styles.card}>
            <div className={styles.header}>
                <FileText size={16} />
                Papers Collected
                <span className={styles.count}>{papers.length}</span>
            </div>
            <ul className={styles.list}>
                {papers.map((p) => (
                    <li key={p.id} className={styles.item}>
                        <span className={styles.title}>{p.title}</span>
                        <span className={styles.source}>{p.source}</span>
                        {p.relevance_score != null && (
                            <span className={styles.score}>
                                {p.relevance_score.toFixed(0)}
                            </span>
                        )}
                    </li>
                ))}
            </ul>
        </div>
    );
}
