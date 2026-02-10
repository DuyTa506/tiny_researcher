import api from './api';
import type {
    Paper,
    StudyCard,
    ScreeningRecord,
    EvidenceSpan,
} from '@/lib/types';

export interface PaperFilters {
    status?: string;
    source?: string;
    min_score?: number;
    max_score?: number;
    keyword?: string;
    plan_id?: string;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface PaperCreateRequest {
    title: string;
    abstract?: string;
    authors?: string[];
    source?: string;
    url?: string;
    pdf_url?: string;
    arxiv_id?: string;
    doi?: string;
}

export const paperService = {
    list: (filters?: PaperFilters) =>
        api.get<PaginatedResponse<Paper>>('/papers', { params: filters }),

    getById: (id: string) =>
        api.get<Paper>(`/papers/${id}`),

    create: (data: PaperCreateRequest) =>
        api.post<{ id: string; message: string }>('/papers', data),

    update: (id: string, data: Partial<PaperCreateRequest & { relevance_score?: number; notes?: string }>) =>
        api.put<{ message: string }>(`/papers/${id}`, data),

    delete: (id: string) =>
        api.delete<{ message: string }>(`/papers/${id}`),

    getStudyCard: (paperId: string) =>
        api.get<StudyCard>(`/papers/${paperId}/study-card`),

    getScreeningRecord: (paperId: string) =>
        api.get<ScreeningRecord>(`/papers/${paperId}/screening`),

    getEvidenceSpans: (paperId: string) =>
        api.get<EvidenceSpan[]>(`/papers/${paperId}/evidence-spans`),
};
