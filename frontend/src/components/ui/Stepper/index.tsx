import { Check, Pause, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import styles from './styles.module.css';

export type StepStatus = 'pending' | 'active' | 'paused' | 'complete' | 'error';

export interface StepItem {
    key: string;
    label: string;
    status: StepStatus;
    detail?: string;
    progress?: number;
    total?: number;
}

interface StepperProps {
    steps: StepItem[];
    className?: string;
}

function StepIcon({ status, index }: { status: StepStatus; index: number }) {
    switch (status) {
        case 'complete':
            return <Check size={14} strokeWidth={3} />;
        case 'paused':
            return <Pause size={12} />;
        case 'error':
            return <AlertCircle size={14} />;
        default:
            return <span>{index + 1}</span>;
    }
}

export default function Stepper({ steps, className }: StepperProps) {
    return (
        <div className={cn(styles.stepper, className)} role="list">
            {steps.map((step, i) => (
                <div
                    key={step.key}
                    className={cn(styles.step, styles[step.status])}
                    role="listitem"
                    aria-current={step.status === 'active' ? 'step' : undefined}
                >
                    <div className={styles.indicator}>
                        <div className={styles.circle}>
                            <StepIcon status={step.status} index={i} />
                        </div>
                        <div className={styles.line} />
                    </div>
                    <div className={styles.content}>
                        <div className={styles.stepLabel}>{step.label}</div>
                        {step.detail && (
                            <div className={styles.stepDetail}>{step.detail}</div>
                        )}
                        {step.status === 'active' &&
                            step.progress !== undefined &&
                            step.total !== undefined &&
                            step.total > 0 && (
                                <div className={styles.progressBar}>
                                    <div
                                        className={styles.progressFill}
                                        style={{
                                            width: `${Math.round((step.progress / step.total) * 100)}%`,
                                        }}
                                    />
                                </div>
                            )}
                    </div>
                </div>
            ))}
        </div>
    );
}
