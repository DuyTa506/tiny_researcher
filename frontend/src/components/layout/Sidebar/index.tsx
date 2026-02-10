'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    LayoutDashboard,
    Microscope,
    FileText,
    BookOpen,
    Menu,
    Beaker,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { NAV_ITEMS } from '@/lib/constants';
import styles from './styles.module.css';

const iconMap: Record<string, React.ReactNode> = {
    LayoutDashboard: <LayoutDashboard size={20} />,
    Microscope: <Microscope size={20} />,
    FileText: <FileText size={20} />,
    BookOpen: <BookOpen size={20} />,
};

export function MobileMenuButton() {
    return null; // Handled by Sidebar's internal toggle
}

export default function Sidebar() {
    const pathname = usePathname();
    const [isOpen, setIsOpen] = useState(false);

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
                />
            )}

            {/* Sidebar */}
            <aside className={cn(styles.sidebar, isOpen && styles.open)}>
                <div className={styles.logo}>
                    <div className={styles.logoIcon}>
                        <Beaker size={18} />
                    </div>
                    <span className={styles.logoText}>Research AI</span>
                </div>

                <nav className={styles.nav}>
                    {NAV_ITEMS.map((item) => {
                        const isActive =
                            item.path === '/'
                                ? pathname === '/'
                                : pathname.startsWith(item.path);

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
                                <span className={styles.navLabel}>{item.label}</span>
                            </Link>
                        );
                    })}
                </nav>
            </aside>
        </>
    );
}
