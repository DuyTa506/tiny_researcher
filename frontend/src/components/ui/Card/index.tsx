import { type ReactNode, type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import styles from './styles.module.css';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    glass?: boolean;
    hoverable?: boolean;
    header?: ReactNode;
    footer?: ReactNode;
    children: ReactNode;
}

export default function Card({
    glass = false,
    hoverable = false,
    header,
    footer,
    children,
    className,
    ...props
}: CardProps) {
    return (
        <div
            className={cn(
                styles.card,
                glass && styles.glass,
                hoverable && styles.hoverable,
                className
            )}
            {...props}
        >
            {header && <div className={styles.header}>{header}</div>}
            {children}
            {footer && <div className={styles.footer}>{footer}</div>}
        </div>
    );
}
