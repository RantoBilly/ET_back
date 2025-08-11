import api from '../config/api';
import Cookies from 'js-cookie';
import { LoginCredentials, AuthTokens, User } from '../types';

class AuthService {
  async login(credentials: LoginCredentials): Promise<{ tokens: AuthTokens; user: User }> {
    const response = await api.post('/auth/login/', credentials);
    const { access, refresh, user } = response.data;

    // Stocker les tokens dans les cookies
    Cookies.set('access_token', access, { expires: 1 });
    Cookies.set('refresh_token', refresh, { expires: 7 });

    return { tokens: { access, refresh }, user };
  }

  async logout(): Promise<void> {
    try {
      const refreshToken = Cookies.get('refresh_token');
      if (refreshToken) {
        await api.post('/auth/logout/', { refresh: refreshToken });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Supprimer les tokens même si la requête échoue
      Cookies.remove('access_token');
      Cookies.remove('refresh_token');
    }
  }

  async getCurrentUser(): Promise<User> {
    const response = await api.get('/auth/me/');
    return response.data;
  }

  async refreshToken(): Promise<string> {
    const refreshToken = Cookies.get('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await api.post('/api/token/refresh/', {
      refresh: refreshToken,
    });

    const { access } = response.data;
    Cookies.set('access_token', access, { expires: 1 });

    return access;
  }

  isAuthenticated(): boolean {
    return !!Cookies.get('access_token');
  }

  getAccessToken(): string | undefined {
    return Cookies.get('access_token');
  }
}

export const authService = new AuthService();