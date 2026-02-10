'use client';

import {
    createContext,
    useContext,
    useState,
    useCallback,
    useEffect,
    type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import {
    CheckCircle,
    AlertCircle,
    AlertTriangle,
    Info,
    X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import styles from './styles.module.css';

type ToastVariant = 'success' | 'error' | 'warning' | 'info';

interface Toast {
    id: string;
    variant: ToastVariant;
    title?: string;
    message: string;
}

interface ToastContextValue {
    toast: (variant: ToastVariant, message: string, title?: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
    toast: () => { },
});

export function useToast() {
    return useContext(ToastContext);
}

const icons: Record<ToastVariant, ReactNode> = {
    success: <CheckCircle size={18} />,
    error: <AlertCircle size={18} />,
    warning: <AlertTriangle size={18} />,
    info: <Info size={18} />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const addToast = useCallback(
        (variant: ToastVariant, message: string, title?: string) => {
            const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
            setToasts((prev) => [...prev, { id, variant, title, message }]);
            setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== id));
            }, 4000);
        },
        []
    );

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ toast: addToast }}>
            {children}
            {mounted &&
                createPortal(
                    <div className={styles.container} aria-live="polite">
                        {toasts.map((t) => (
                            <div
                                key={t.id}
                                className={cn(styles.toast, styles[t.variant])}
                                role="alert"
                            >
                                <span className={styles.icon}>{icons[t.variant]}</span>
                                <div className={styles.content}>
                                    {t.title && <div className={styles.title}>{t.title}</div>}
                                    <div className={styles.message}>{t.message}</div>
                                </div>
                                <button
                                    className={styles.close}
                                    onClick={() => removeToast(t.id)}
                                    aria-label="Dismiss"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        ))}
                    </div>,
                    document.body
                )}
        </ToastContext.Provider>
    );
}
