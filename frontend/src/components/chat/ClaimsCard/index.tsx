'use client';

import { Lightbulb, Compass } from 'lucide-react';
import type { Claim, FutureDirection } from '@/lib/types';
import styles from './styles.module.css';

interface ClaimsCardProps {
    claims?: Claim[];
    gaps?: FutureDirection[];
}

export default function ClaimsCard({ claims, gaps }: ClaimsCardProps) {
    const showClaims = claims && claims.length > 0;
    const showGaps = gaps && gaps.length > 0;

    return (
        <div className={styles.card}>
            {showClaims && (
                <>
                    <div className={styles.header}>
                        <Lightbulb size={16} />
                        Claims Generated
                        <span className={styles.count}>{claims.length}</span>
                    </div>
                    <ul className={styles.list}>
                        {claims.map((c) => (
                            <li key={c.claim_id} className={styles.claim}>
                                <div className={styles.claimText}>{c.claim_text}</div>
                                <div className={styles.claimMeta}>
                                    <span className={styles.salience}>
                                        <span className={styles.salienceBar}>
                                            <span
                                                className={styles.salienceFill}
                                                style={{ width: `${c.salience_score * 100}%` }}
                                            />
                                        </span>
                                        {(c.salience_score * 100).toFixed(0)}%
                                    </span>
                                    {c.uncertainty_flag && (
                                        <span className={styles.uncertainty}>⚠️ Uncertain</span>
                                    )}
                                </div>
                            </li>
                        ))}
                    </ul>
                </>
            )}
            {showGaps && (
                <>
                    <div className={styles.header} style={{ borderTop: showClaims ? '1px solid var(--border)' : undefined }}>
                        <Compass size={16} />
                        Future Directions
                        <span className={styles.count}>{gaps.length}</span>
                    </div>
                    <ul className={styles.list}>
                        {gaps.map((g, i) => (
                            <li key={i} className={styles.gap}>
                                <div className={styles.gapTitle}>{g.title}</div>
                                <div className={styles.gapDesc}>{g.description}</div>
                                {g.theme && <span className={styles.gapTheme}>{g.theme}</span>}
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
