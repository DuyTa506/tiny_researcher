'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authService } from '@/services/auth';
import styles from '../../login/styles.module.css';

function VerifyEmailContent() {
    const searchParams = useSearchParams();
    const token = searchParams.get('token') || '';
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
    const [message, setMessage] = useState('');

    useEffect(() => {
        if (!token) {
            setStatus('error');
            setMessage('Invalid verification link');
            return;
        }

        authService
            .verifyEmail(token)
            .then(() => {
                setStatus('success');
                setMessage('Your email has been verified successfully!');
            })
            .catch((err) => {
                setStatus('error');
                setMessage(err instanceof Error ? err.message : 'Verification failed');
            });
    }, [token]);

    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <div className={styles.header}>
                    <h1 className={styles.title}>
                        {status === 'loading' ? 'Verifying...' : status === 'success' ? 'Email Verified' : 'Verification Failed'}
                    </h1>
                    <p className={styles.subtitle}>{message}</p>
                </div>
                <div className={styles.footer}>
                    <Link href={status === 'success' ? '/' : '/login'}>
                        {status === 'success' ? 'Go to Dashboard' : 'Back to sign in'}
                    </Link>
                </div>
            </div>
        </div>
    );
}

export default function VerifyEmailPage() {
    return (
        <Suspense>
            <VerifyEmailContent />
        </Suspense>
    );
}
