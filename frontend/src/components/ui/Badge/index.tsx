import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import styles from './styles.module.css';

type BadgeVariant = 'high' | 'medium' | 'low' | 'none' | 'info';

interface BadgeProps {
    variant?: BadgeVariant;
    dot?: boolean;
    children: ReactNode;
    className?: string;
}

export default function Badge({
    variant = 'none',
    dot = false,
    children,
    className,
}: BadgeProps) {
    return (
        <span className={cn(styles.badge, styles[variant], className)}>
            {dot && <span className={styles.dot} />}
            {children}
        </span>
    );
}
