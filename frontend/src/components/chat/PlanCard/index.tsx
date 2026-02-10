'use client';

import { Map, CheckCircle } from 'lucide-react';
import type { ResearchPlan } from '@/lib/types';
import styles from './styles.module.css';

interface PlanCardProps {
    plan: ResearchPlan;
}

export default function PlanCard({ plan }: PlanCardProps) {
    return (
        <div className={styles.card}>
            <div className={styles.header}>
                <Map size={16} />
                Research Plan: {plan.topic}
                {plan.mode && <span className={styles.mode}>{plan.mode}</span>}
            </div>
            {plan.summary && (
                <div className={styles.summary}>{plan.summary}</div>
            )}
            <ol className={styles.steps}>
                {plan.steps.map((step) => (
                    <li key={step.id} className={styles.step}>
                        <span
                            className={`${styles.stepNumber} ${step.completed ? styles.stepCompleted : ''}`}
                        >
                            {step.completed ? <CheckCircle size={12} /> : step.id}
                        </span>
                        <div className={styles.stepBody}>
                            <div className={styles.stepTitle}>{step.title}</div>
                            <div className={styles.stepDesc}>{step.description}</div>
                            <div className={styles.stepMeta}>
                                {step.tool && <span className={styles.tag}>🔧 {step.tool}</span>}
                                {step.queries.slice(0, 2).map((q, i) => (
                                    <span key={i} className={styles.tag}>🔍 {q}</span>
                                ))}
                            </div>
                        </div>
                    </li>
                ))}
            </ol>
        </div>
    );
}
