'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import {
    LayoutDashboard,
    Microscope,
    FileText,
    BookOpen,
    Menu,
    Beaker,
    MessageSquare,
    User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { NAV_ITEMS } from '@/lib/constants';
import styles from './styles.module.css';

const iconMap: Record<string, React.ReactNode> = {
    LayoutDashboard: <LayoutDashboard size={20} />,
    Microscope: <Microscope size={20} />,
    FileText: <FileText size={20} />,
    BookOpen: <BookOpen size={20} />,
    MessageSquare: <MessageSquare size={20} />,
    User: <User size={20} />,
};

/* Map nav paths to translation keys */
const navI18nKeyMap: Record<string, string> = {
    '/': 'nav.dashboard',
    '/research': 'nav.research',
    '/sessions': 'nav.sessions',
    '/papers': 'nav.papers',
    '/reports': 'nav.reports',
    '/profile': 'nav.profile',
};

export function MobileMenuButton() {
    return null; // Handled by Sidebar's internal toggle
}

export default function Sidebar() {
    const pathname = usePathname();
    const [isOpen, setIsOpen] = useState(false);
    const { t } = useTranslation();

    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isOpen]);

    return (
        <>
            {/* Mobile toggle */}
            <button
                className={styles.menuToggle}
                onClick={() => setIsOpen(true)}
                aria-label="Open navigation"
            >
                <Menu size={20} />
            </button>

            {/* Overlay for mobile */}
            {isOpen && (
                <div
                    className={styles.overlay}
                    onClick={() => setIsOpen(false)}
                    onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                            setIsOpen(false);
                        }
                    }}
                    role="presentation"
                    tabIndex={-1}
                />
            )}

            {/* Sidebar */}
            <aside className={cn(styles.sidebar, isOpen && styles.open)}>
                <div className={styles.logo}>
                    <div className={styles.logoIcon}>
                        <Beaker size={18} />
                    </div>
                    <span className={styles.logoText}>{t('app.name')}</span>
                </div>

                <nav className={styles.nav}>
                    {NAV_ITEMS.map((item) => {
                        const isActive =
                            item.path === '/'
                                ? pathname === '/'
                                : pathname.startsWith(item.path);

                        const i18nKey = navI18nKeyMap[item.path];

                        return (
                            <Link
                                key={item.path}
                                href={item.path}
                                className={cn(styles.navItem, isActive && styles.active)}
                                onClick={() => setIsOpen(false)}
                            >
                                <span className={styles.navIcon}>
                                    {iconMap[item.icon]}
                                </span>
                                <span className={styles.navLabel}>
                                    {i18nKey ? t(i18nKey) : item.label}
                                </span>
                            </Link>
                        );
                    })}
                </nav>
            </aside>
        </>
    );
}
