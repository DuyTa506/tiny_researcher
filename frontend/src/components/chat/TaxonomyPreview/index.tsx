'use client';

import { Grid3x3 } from 'lucide-react';
import type { TaxonomyMatrix } from '@/lib/types';
import styles from './styles.module.css';

interface TaxonomyPreviewProps {
    matrix: TaxonomyMatrix;
}

export default function TaxonomyPreview({ matrix }: TaxonomyPreviewProps) {
    return (
        <div className={styles.card}>
            <div className={styles.header}>
                <Grid3x3 size={16} />
                Taxonomy Matrix
                <span className={styles.dims}>
                    {matrix.themes.length} themes × {matrix.columns.length} columns
                </span>
            </div>
            <div className={styles.tableWrap}>
                <table className={styles.table}>
                    <thead>
                        <tr>
                            <th>Theme</th>
                            {matrix.columns.map((col) => (
                                <th key={col}>{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {matrix.themes.map((theme) => (
                            <tr key={theme}>
                                <td>{theme}</td>
                                {matrix.columns.map((col) => {
                                    const cell = matrix.cells.find(
                                        (c) => c.theme === theme && (c.dataset === col || c.metric === col || c.method === col)
                                    );
                                    const isEmpty = !cell || cell.paper_ids.length === 0;
                                    return (
                                        <td key={col} className={isEmpty ? styles.empty : ''}>
                                            {isEmpty
                                                ? <span className={styles.gapBadge}>GAP</span>
                                                : cell.paper_ids.length}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
