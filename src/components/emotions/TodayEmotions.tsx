import React, { useState, useEffect } from 'react';
import { Emotion } from '../../types';
import { emotionService } from '../../services/emotionService';
import EmotionIcon from '../common/EmotionIcon';
import LoadingSpinner from '../common/LoadingSpinner';
import { Sun, Moon, Calendar } from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';

const TodayEmotions: React.FC = () => {
  const [todayEmotions, setTodayEmotions] = useState<{
    morning: Emotion | null;
    evening: Emotion | null;
    can_submit_morning: boolean;
    can_submit_evening: boolean;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTodayEmotions();
  }, []);

  const loadTodayEmotions = async () => {
    try {
      const emotions = await emotionService.getTodayEmotions();
      setTodayEmotions(emotions);
    } catch (error) {
      console.error('Error loading today emotions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="card">
        <LoadingSpinner size="lg" className="py-8" />
      </div>
    );
  }

  const EmotionDisplay: React.FC<{ 
    emotion: Emotion | null; 
    period: 'morning' | 'evening';
    canSubmit: boolean;
  }> = ({ emotion, period, canSubmit }) => {
    const icon = period === 'morning' ? (
      <Sun className="w-5 h-5 text-yellow-500" />
    ) : (
      <Moon className="w-5 h-5 text-blue-500" />
    );
    
    const periodText = period === 'morning' ? 'Matin' : 'Soir';

    return (
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {icon}
          <span className="font-medium text-gray-900">{periodText}</span>
        </div>
        
        {emotion ? (
          <div className="flex items-center space-x-2">
            <EmotionIcon emotion={emotion.emotion_type_name} size={20} />
            <span className="text-sm font-medium text-gray-700 capitalize">
              {emotion.emotion_type_name.toLowerCase()}
            </span>
            <span className="text-xs text-gray-500">
              ({format(new Date(emotion.date), 'HH:mm')})
            </span>
          </div>
        ) : (
          <span className="text-sm text-gray-500">
            {canSubmit ? 'Non soumise' : 'Période passée'}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="card">
      <div className="flex items-center space-x-2 mb-6">
        <Calendar className="w-6 h-6 text-primary-600" />
        <h2 className="text-xl font-bold text-gray-900">
          Émotions d'aujourd'hui
        </h2>
        <span className="text-sm text-gray-500 ml-auto">
          {format(new Date(), 'EEEE d MMMM yyyy', { locale: fr })}
        </span>
      </div>

      <div className="space-y-3">
        <EmotionDisplay
          emotion={todayEmotions?.morning || null}
          period="morning"
          canSubmit={todayEmotions?.can_submit_morning || false}
        />
        <EmotionDisplay
          emotion={todayEmotions?.evening || null}
          period="evening"
          canSubmit={todayEmotions?.can_submit_evening || false}
        />
      </div>

      {(!todayEmotions?.morning && !todayEmotions?.evening) && (
        <div className="text-center py-6">
          <p className="text-gray-500">
            Aucune émotion enregistrée aujourd'hui
          </p>
        </div>
      )}
    </div>
  );
};

export default TodayEmotions;