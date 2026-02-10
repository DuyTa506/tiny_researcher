'use client';

import { Search, Sun, Moon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@/app/providers';
import LanguageSwitcher from '@/components/ui/LanguageSwitcher';
import styles from './styles.module.css';

interface HeaderProps {
    title: string;
}

export default function Header({ title }: HeaderProps) {
    const { theme, toggleTheme } = useTheme();
    const { t } = useTranslation();

    return (
        <header className={styles.header}>
            <div className={styles.left}>
                <h1 className={styles.title}>{title}</h1>
            </div>

            <div className={styles.right}>
                <div className={styles.search}>
                    <Search size={16} className={styles.searchIcon} />
                    <input
                        type="search"
                        className={styles.searchInput}
                        placeholder={t('header.searchPlaceholder')}
                        aria-label="Search"
                    />
                </div>

                <LanguageSwitcher />

                <button
                    className={styles.themeToggle}
                    onClick={toggleTheme}
                    aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                >
                    {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
                </button>
            </div>
        </header>
    );
}
