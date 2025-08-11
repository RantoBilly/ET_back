import api from '../config/api';
import { Cluster, Entity, Department, Service, ApiResponse } from '../types';

class OrganizationService {
  // Manager Overview
  async getManagerOverview(): Promise<any> {
    const response = await api.get('/manager/');
    return response.data;
  }

  // Department Director Overview
  async getDepartmentOverview(): Promise<any> {
    const response = await api.get('/department/');
    return response.data;
  }

  async getDepartmentReport(format: 'pdf' | 'json' = 'json'): Promise<any> {
    const response = await api.get(`/department/report/?format=${format}`, {
      responseType: format === 'pdf' ? 'blob' : 'json',
    });
    return response.data;
  }

  // Entity Director Overview
  async getEntityOverview(): Promise<any> {
    const response = await api.get('/entity/');
    return response.data;
  }

  async getEntityReport(format: 'pdf' | 'json' = 'json'): Promise<any> {
    const response = await api.get(`/entity/report/?format=${format}`, {
      responseType: format === 'pdf' ? 'blob' : 'json',
    });
    return response.data;
  }

  // Pole Director Overview
  async getClusterOverview(): Promise<any> {
    const response = await api.get('/cluster/');
    return response.data;
  }

  async getClusterReport(format: 'pdf' | 'json' = 'json'): Promise<any> {
    const response = await api.get(`/cluster/report/?format=${format}`, {
      responseType: format === 'pdf' ? 'blob' : 'json',
    });
    return response.data;
  }

  // DRH Overview
  async getDrhOverview(): Promise<any> {
    const response = await api.get('/drh/');
    return response.data;
  }

  async getDrhReport(format: 'pdf' | 'json' = 'json'): Promise<any> {
    const response = await api.get(`/drh/report/?format=${format}`, {
      responseType: format === 'pdf' ? 'blob' : 'json',
    });
    return response.data;
  }

  // Utility method to download PDF reports
  downloadReport(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
}

export const organizationService = new OrganizationService();