import api from './api';
import type { Report, Claim, TaxonomyMatrix } from '@/lib/types';

export interface ReportFilters {
    page?: number;
    page_size?: number;
    keyword?: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export const reportService = {
    list: (filters?: ReportFilters) =>
        api.get<PaginatedResponse<Report>>('/reports', { params: filters }),

    getById: (id: string) =>
        api.get<Report>(`/reports/${id}`),

    update: (id: string, data: { title?: string; content?: string }) =>
        api.put<{ message: string }>(`/reports/${id}`, data),

    delete: (id: string) =>
        api.delete<{ message: string }>(`/reports/${id}`),

    export: (id: string, format: 'markdown' | 'html' = 'markdown') =>
        api.get(`/reports/${id}/export`, {
            params: { format },
            responseType: 'blob',
        }),

    getClaims: (reportId: string) =>
        api.get<Claim[]>(`/reports/${reportId}/claims`),

    getTaxonomyMatrix: (reportId: string) =>
        api.get<TaxonomyMatrix>(`/reports/${reportId}/taxonomy`),

    getCitationAuditStatus: (reportId: string) =>
        api.get<{ total: number; verified: number; uncertain: number }>(
            `/reports/${reportId}/citation-audit`
        ),
};
