'use client';

import { useState } from 'react';
import Link from 'next/link';
import { authService } from '@/services/auth';
import styles from '../../login/styles.module.css';

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [sent, setSent] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await authService.requestPasswordReset(email);
            setSent(true);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to send reset email');
        } finally {
            setLoading(false);
        }
    };

    if (sent) {
        return (
            <div className={styles.container}>
                <div className={styles.card}>
                    <div className={styles.header}>
                        <h1 className={styles.title}>Check your email</h1>
                        <p className={styles.subtitle}>
                            If an account with that email exists, we&apos;ve sent a password reset link.
                        </p>
                    </div>
                    <div className={styles.footer}>
                        <Link href="/login">Back to sign in</Link>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <div className={styles.header}>
                    <h1 className={styles.title}>Forgot password?</h1>
                    <p className={styles.subtitle}>Enter your email to receive a reset link</p>
                </div>

                <form onSubmit={handleSubmit} className={styles.form}>
                    {error && <div className={styles.error}>{error}</div>}

                    <div className={styles.field}>
                        <label htmlFor="email">Email</label>
                        <input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="you@example.com"
                            required
                            autoFocus
                        />
                    </div>

                    <button type="submit" className={styles.submitBtn} disabled={loading}>
                        {loading ? 'Sending...' : 'Send reset link'}
                    </button>
                </form>

                <div className={styles.footer}>
                    <Link href="/login">Back to sign in</Link>
                </div>
            </div>
        </div>
    );
}
