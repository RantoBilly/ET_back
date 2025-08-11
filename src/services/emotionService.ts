import api from '../config/api';
import { Emotion, EmotionType, EmotionSubmission, ApiResponse } from '../types';

class EmotionService {
  async getEmotionTypes(): Promise<EmotionType[]> {
    const response = await api.get('/emotions/emotion-types/');
    return response.data;
  }

  async submitEmotion(emotionData: EmotionSubmission): Promise<Emotion> {
    const response = await api.post('/emotions/', emotionData);
    return response.data;
  }

  async getMyEmotions(params?: {
    date?: string;
    week_number?: number;
    month?: number;
    year?: number;
    half_day?: 'morning' | 'evening';
  }): Promise<ApiResponse<Emotion>> {
    const response = await api.get('/emotions/', { params });
    return response.data;
  }

  async getEmotionOverview(period: 'today' | 'week' | 'month' = 'today'): Promise<any> {
    const response = await api.get(`/emotion-overview/?period=${period}`);
    return response.data;
  }

  async getTodayEmotions(): Promise<{
    morning: Emotion | null;
    evening: Emotion | null;
    can_submit_morning: boolean;
    can_submit_evening: boolean;
  }> {
    const response = await api.get('/emotions/today/');
    return response.data;
  }

  async getEmotionHistory(params?: {
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }): Promise<ApiResponse<Emotion>> {
    const response = await api.get('/emotions/history/', { params });
    return response.data;
  }
}

export const emotionService = new EmotionService();