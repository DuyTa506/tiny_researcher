'use client';

import { useEffect, useRef } from 'react';
import type { ActivityEntry } from '@/lib/types';
import styles from './styles.module.css';

interface ActivityLogProps {
    entries: ActivityEntry[];
}

function formatTime(iso: string) {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function ActivityLog({ entries }: ActivityLogProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [entries.length]);

    if (entries.length === 0) {
        return (
            <div className={styles.container}>
                <div className={styles.title}>Activity Log</div>
                <div className={styles.empty}>No activity yet</div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            <div className={styles.title}>Activity Log</div>
            {entries.map((e) => (
                <div key={e.id} className={styles.entry}>
                    <span className={styles.timestamp}>{formatTime(e.timestamp)}</span>
                    <span className={styles.icon}>{e.icon}</span>
                    <span className={styles.text} title={e.text}>{e.text}</span>
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
