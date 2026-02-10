import { cn } from '@/lib/utils';
import styles from './styles.module.css';

interface SkeletonProps {
    width?: string | number;
    height?: string | number;
    variant?: 'text' | 'heading' | 'circle' | 'rect';
    className?: string;
}

export default function Skeleton({
    width,
    height,
    variant = 'rect',
    className,
}: SkeletonProps) {
    return (
        <div
            className={cn(
                styles.skeleton,
                variant === 'text' && styles.text,
                variant === 'heading' && styles.heading,
                variant === 'circle' && styles.circle,
                className
            )}
            style={{ width, height }}
            aria-hidden="true"
        />
    );
}
