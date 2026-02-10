'use client';

import { type ReactNode } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import styles from './styles.module.css';

interface AppShellProps {
    title: string;
    children: ReactNode;
}

export default function AppShell({ title, children }: AppShellProps) {
    return (
        <div className={styles.container}>
            <Sidebar />
            <div className={styles.main}>
                <Header title={title} />
                <main className={styles.content}>{children}</main>
            </div>
        </div>
    );
}
