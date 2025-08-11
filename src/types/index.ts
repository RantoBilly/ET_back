export interface User {
  id: number;
  email_address: string;
  first_name: string;
  last_name: string;
  role: 'employee' | 'manager' | 'department_director' | 'entity_director' | 'pole_director' | 'admin';
  cluster_name?: string;
  entity_name?: string;
  department_name?: string;
  service_name?: string;
  manager_name?: string;
  is_active: boolean;
  is_staff: boolean;
}

export interface EmotionType {
  id: number;
  name: 'HAPPY' | 'SAD' | 'NEUTRAL' | 'ANGRY' | 'EXCITED' | 'ANXIOUS';
  emoticon: string;
  degree: number;
  created_at: string;
}

export interface Emotion {
  id: number;
  emotion_type: number;
  emotion_type_name: string;
  emotion_degree: number;
  collaborator: number;
  collaborator_name: string;
  date: string;
  week_number: number;
  month: number;
  year: number;
  half_day: 'morning' | 'evening';
  date_period: string;
}

export interface EmotionSummary {
  average_degree: number | null;
  emotion: string;
}

export interface OrganizationUnit {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  emotion_summary: {
    today: EmotionSummary;
    week: EmotionSummary;
    month: EmotionSummary;
  };
}

export interface Cluster extends OrganizationUnit {}
export interface Entity extends OrganizationUnit {
  cluster_name?: string;
}
export interface Department extends OrganizationUnit {
  entity_name?: string;
}
export interface Service extends OrganizationUnit {
  department_name?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginCredentials {
  email_address: string;
  password: string;
}

export interface ApiResponse<T> {
  results?: T[];
  count?: number;
  next?: string;
  previous?: string;
}

export interface EmotionSubmission {
  emotion_type: number;
  date?: string;
}

export type EmotionPeriod = 'today' | 'week' | 'month';
export type HalfDay = 'morning' | 'evening';