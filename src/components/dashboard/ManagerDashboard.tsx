import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { organizationService } from '../../services/organizationService';
import EmotionSummaryCard from './EmotionSummaryCard';
import LoadingSpinner from '../common/LoadingSpinner';
import { Users, TrendingUp, Calendar, Clock, Building } from 'lucide-react';

const ManagerDashboard: React.FC = () => {
  const { user } = useAuth();
  const [overview, setOverview] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadOverview();
  }, []);

  const loadOverview = async () => {
    try {
      const data = await organizationService.getManagerOverview();
      setOverview(data);
    } catch (error) {
      console.error('Error loading manager overview:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold mb-2">
          Tableau de bord Manager 📊
        </h1>
        <p className="text-blue-100">
          Vue d'ensemble des émotions de votre équipe
        </p>
        {user?.service_name && (
          <p className="text-blue-200 text-sm mt-2">
            Service: {user.service_name}
          </p>
        )}
      </div>

      {overview && (
        <>
          {/* Statistiques générales */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="card bg-gradient-to-br from-green-50 to-green-100 border-green-200">
              <div className="flex items-center space-x-3">
                <Users className="w-8 h-8 text-green-600" />
                <div>
                  <p className="text-2xl font-bold text-green-900">
                    {overview.total_collaborators || 0}
                  </p>
                  <p className="text-sm text-green-700">Collaborateurs</p>
                </div>
              </div>
            </div>

            <div className="card bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
              <div className="flex items-center space-x-3">
                <TrendingUp className="w-8 h-8 text-blue-600" />
                <div>
                  <p className="text-2xl font-bold text-blue-900">
                    {overview.emotions_today || 0}
                  </p>
                  <p className="text-sm text-blue-700">Émotions aujourd'hui</p>
                </div>
              </div>
            </div>

            <div className="card bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
              <div className="flex items-center space-x-3">
                <Calendar className="w-8 h-8 text-purple-600" />
                <div>
                  <p className="text-2xl font-bold text-purple-900">
                    {overview.emotions_this_week || 0}
                  </p>
                  <p className="text-sm text-purple-700">Cette semaine</p>
                </div>
              </div>
            </div>

            <div className="card bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
              <div className="flex items-center space-x-3">
                <Clock className="w-8 h-8 text-orange-600" />
                <div>
                  <p className="text-2xl font-bold text-orange-900">
                    {overview.emotions_this_month || 0}
                  </p>
                  <p className="text-sm text-orange-700">Ce mois</p>
                </div>
              </div>
            </div>
          </div>

          {/* Résumé des émotions */}
          {overview.emotion_summary && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <EmotionSummaryCard
                title="Aujourd'hui"
                summary={overview.emotion_summary.today}
                icon={<Calendar className="w-5 h-5 text-primary-600" />}
              />
              <EmotionSummaryCard
                title="Cette semaine"
                summary={overview.emotion_summary.week}
                icon={<TrendingUp className="w-5 h-5 text-primary-600" />}
              />
              <EmotionSummaryCard
                title="Ce mois"
                summary={overview.emotion_summary.month}
                icon={<Clock className="w-5 h-5 text-primary-600" />}
              />
            </div>
          )}

          {/* Liste des collaborateurs */}
          {overview.collaborators && overview.collaborators.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                <Users className="w-5 h-5 text-primary-600" />
                <span>Équipe</span>
              </h3>
              <div className="space-y-3">
                {overview.collaborators.map((collaborator: any) => (
                  <div
                    key={collaborator.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="font-medium text-gray-900">
                        {collaborator.first_name} {collaborator.last_name}
                      </p>
                      <p className="text-sm text-gray-600">
                        {collaborator.email_address}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-gray-700">
                        Émotion du jour: {collaborator.emotion_today || 'Non renseignée'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ManagerDashboard;