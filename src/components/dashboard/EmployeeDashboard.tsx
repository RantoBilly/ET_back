import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { emotionService } from '../../services/emotionService';
import EmotionSubmissionForm from '../emotions/EmotionSubmissionForm';
import TodayEmotions from '../emotions/TodayEmotions';
import EmotionHistory from '../emotions/EmotionHistory';
import EmotionSummaryCard from './EmotionSummaryCard';
import LoadingSpinner from '../common/LoadingSpinner';
import { Calendar, TrendingUp, Clock } from 'lucide-react';

const EmployeeDashboard: React.FC = () => {
  const { user } = useAuth();
  const [emotionOverview, setEmotionOverview] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    loadEmotionOverview();
  }, [refreshKey]);

  const loadEmotionOverview = async () => {
    try {
      const overview = await emotionService.getEmotionOverview();
      setEmotionOverview(overview);
    } catch (error) {
      console.error('Error loading emotion overview:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmissionSuccess = () => {
    setRefreshKey(prev => prev + 1);
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
      {/* En-tête de bienvenue */}
      <div className="bg-gradient-to-r from-primary-600 to-primary-700 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold mb-2">
          Bonjour, {user?.first_name}! 👋
        </h1>
        <p className="text-primary-100">
          Comment vous sentez-vous aujourd'hui ? Partagez votre émotion avec nous.
        </p>
      </div>

      {/* Résumé des émotions */}
      {emotionOverview && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <EmotionSummaryCard
            title="Aujourd'hui"
            summary={emotionOverview.today}
            icon={<Calendar className="w-5 h-5 text-primary-600" />}
          />
          <EmotionSummaryCard
            title="Cette semaine"
            summary={emotionOverview.week}
            icon={<TrendingUp className="w-5 h-5 text-primary-600" />}
          />
          <EmotionSummaryCard
            title="Ce mois"
            summary={emotionOverview.month}
            icon={<Clock className="w-5 h-5 text-primary-600" />}
          />
        </div>
      )}

      {/* Grille principale */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Colonne gauche */}
        <div className="space-y-6">
          <EmotionSubmissionForm onSubmissionSuccess={handleSubmissionSuccess} />
          <TodayEmotions key={refreshKey} />
        </div>

        {/* Colonne droite */}
        <div>
          <EmotionHistory key={refreshKey} />
        </div>
      </div>
    </div>
  );
};

export default EmployeeDashboard;