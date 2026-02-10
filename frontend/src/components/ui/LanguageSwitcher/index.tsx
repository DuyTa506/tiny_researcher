'use client';

import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';
import styles from './LanguageSwitcher.module.css';

const LANGUAGES = [
    { code: 'en', label: 'EN' },
    { code: 'vi', label: 'VI' },
] as const;

export default function LanguageSwitcher() {
    const { i18n } = useTranslation();

    return (
        <div className={styles.switcher}>
            <Globe size={15} className={styles.icon} />
            {LANGUAGES.map((lang) => (
                <button
                    key={lang.code}
                    className={`${styles.btn} ${i18n.language === lang.code ? styles.active : ''}`}
                    onClick={() => i18n.changeLanguage(lang.code)}
                    aria-label={`Switch to ${lang.label}`}
                >
                    {lang.label}
                </button>
            ))}
        </div>
    );
}
