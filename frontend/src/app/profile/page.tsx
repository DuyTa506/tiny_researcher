'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { authService } from '@/services/auth';
import AppShell from '@/components/layout/AppShell';
import styles from './styles.module.css';

export default function ProfilePage() {
    const { user, refreshUser, logout } = useAuth();
    const [fullName, setFullName] = useState(user?.full_name || '');
    const [username, setUsername] = useState(user?.username || '');
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');

    // Password change
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw] = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [pwMessage, setPwMessage] = useState('');
    const [pwSaving, setPwSaving] = useState(false);

    if (!user) return null;

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage('');
        setSaving(true);
        try {
            await authService.updateProfile({ full_name: fullName, username });
            await refreshUser();
            setMessage('Profile updated');
        } catch (err: unknown) {
            setMessage(err instanceof Error ? err.message : 'Update failed');
        } finally {
            setSaving(false);
        }
    };

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        setPwMessage('');

        if (newPw !== confirmPw) {
            setPwMessage('Passwords do not match');
            return;
        }

        setPwSaving(true);
        try {
            await authService.changePassword(currentPw, newPw);
            setPwMessage('Password changed successfully');
            setCurrentPw('');
            setNewPw('');
            setConfirmPw('');
        } catch (err: unknown) {
            setPwMessage(err instanceof Error ? err.message : 'Failed to change password');
        } finally {
            setPwSaving(false);
        }
    };

    return (
        <AppShell title="Profile">
            <div className={styles.page}>
                <div className={styles.section}>
                    <h2 className={styles.sectionTitle}>Account</h2>
                    <form onSubmit={handleSave} className={styles.form}>
                        <div className={styles.field}>
                            <label>Email</label>
                            <input type="email" value={user.email} disabled />
                        </div>
                        <div className={styles.field}>
                            <label>Username</label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                            />
                        </div>
                        <div className={styles.field}>
                            <label>Full Name</label>
                            <input
                                type="text"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                            />
                        </div>
                        <div className={styles.field}>
                            <label>Role</label>
                            <input type="text" value={user.role} disabled />
                        </div>
                        {message && <p className={styles.message}>{message}</p>}
                        <button type="submit" className={styles.btn} disabled={saving}>
                            {saving ? 'Saving...' : 'Save changes'}
                        </button>
                    </form>
                </div>

                <div className={styles.section}>
                    <h2 className={styles.sectionTitle}>Change Password</h2>
                    <form onSubmit={handlePasswordChange} className={styles.form}>
                        <div className={styles.field}>
                            <label>Current Password</label>
                            <input
                                type="password"
                                value={currentPw}
                                onChange={(e) => setCurrentPw(e.target.value)}
                                required
                            />
                        </div>
                        <div className={styles.field}>
                            <label>New Password</label>
                            <input
                                type="password"
                                value={newPw}
                                onChange={(e) => setNewPw(e.target.value)}
                                required
                                minLength={8}
                            />
                        </div>
                        <div className={styles.field}>
                            <label>Confirm New Password</label>
                            <input
                                type="password"
                                value={confirmPw}
                                onChange={(e) => setConfirmPw(e.target.value)}
                                required
                            />
                        </div>
                        {pwMessage && <p className={styles.message}>{pwMessage}</p>}
                        <button type="submit" className={styles.btn} disabled={pwSaving}>
                            {pwSaving ? 'Changing...' : 'Change password'}
                        </button>
                    </form>
                </div>

                <div className={styles.section}>
                    <h2 className={styles.sectionTitle}>Usage Statistics</h2>
                    <div className={styles.stats}>
                        <div className={styles.stat}>
                            <span className={styles.statValue}>{user.usage_stats?.papers_collected ?? 0}</span>
                            <span className={styles.statLabel}>Papers Collected</span>
                        </div>
                        <div className={styles.stat}>
                            <span className={styles.statValue}>{user.usage_stats?.reports_generated ?? 0}</span>
                            <span className={styles.statLabel}>Reports Generated</span>
                        </div>
                        <div className={styles.stat}>
                            <span className={styles.statValue}>{user.usage_stats?.research_sessions ?? 0}</span>
                            <span className={styles.statLabel}>Research Sessions</span>
                        </div>
                    </div>
                </div>

                <div className={styles.section}>
                    <button className={styles.logoutBtn} onClick={logout}>
                        Sign out
                    </button>
                </div>
            </div>
        </AppShell>
    );
}
