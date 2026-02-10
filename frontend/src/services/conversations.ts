import api from './api';
import { API_BASE_URL } from '@/lib/constants';
import type { Conversation } from '@/lib/types';

export const conversationService = {
    create: (topic?: string) =>
        api.post<Conversation>('/conversations', { user_id: 'anonymous' }),

    get: (id: string) =>
        api.get<Conversation>(`/conversations/${id}`),

    sendMessage: (id: string, content: string) =>
        api.post(`/conversations/${id}/messages`, { message: content }),

    delete: (id: string) =>
        api.delete(`/conversations/${id}`),

    approveGate: (id: string, gateId: string) =>
        api.post(`/conversations/${id}/gates/${gateId}/approve`),

    rejectGate: (id: string, gateId: string) =>
        api.post(`/conversations/${id}/gates/${gateId}/reject`),

    streamUrl: (id: string) =>
        `${API_BASE_URL}/conversations/${id}/stream`,

    list: () =>
        api.get<{ items: Conversation[]; total: number }>('/conversations'),
};
