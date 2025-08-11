import React, { useState, useEffect } from 'react';
import { EmotionType } from '../../types';
import { emotionService } from '../../services/emotionService';
import EmotionCard from '../common/EmotionCard';
import LoadingSpinner from '../common/LoadingSpinner';
import toast from 'react-hot-toast';
import { Clock, Sun, Moon } from 'lucide-react';

interface EmotionSubmissionFormProps {
  onSubmissionSuccess?: () => void;
}

const EmotionSubmissionForm: React.FC<EmotionSubmissionFormProps> = ({
  onSubmissionSuccess,
}) => {
  const [emotionTypes, setEmotionTypes] = useState<EmotionType[]>([]);
  const [selectedEmotion, setSelectedEmotion] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingTypes, setIsLoadingTypes] = useState(true);
  const [todayEmotions, setTodayEmotions] = useState<any>(null);

  useEffect(() => {
    loadEmotionTypes();
    loadTodayEmotions();
  }, []);

  const loadEmotionTypes = async () => {
    try {
      const types = await emotionService.getEmotionTypes();
      setEmotionTypes(types);
    } catch (error) {
      toast.error('Erreur lors du chargement des types d\'émotions');
    } finally {
      setIsLoadingTypes(false);
    }
  };

  const loadTodayEmotions = async () => {
    try {
      const emotions = await emotionService.getTodayEmotions();
      setTodayEmotions(emotions);
    } catch (error) {
      console.error('Error loading today emotions:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedEmotion) {
      toast.error('Veuillez sélectionner une émotion');
      return;
    }

    try {
      setIsLoading(true);
      await emotionService.submitEmotion({
        emotion_type: selectedEmotion,
      });
      
      toast.success('Émotion enregistrée avec succès!');
      setSelectedEmotion(null);
      await loadTodayEmotions(); // Recharger les émotions du jour
      
      if (onSubmissionSuccess) {
        onSubmissionSuccess();
      }
    } catch (error: any) {
      console.error('Submission error:', error);
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('Erreur lors de l\'enregistrement de l\'émotion');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getCurrentPeriod = () => {
    const hour = new Date().getHours();
    return hour < 12 ? 'morning' : 'evening';
  };

  const canSubmit = () => {
    if (!todayEmotions) return true;
    
    const currentPeriod = getCurrentPeriod();
    return currentPeriod === 'morning' 
      ? todayEmotions.can_submit_morning 
      : todayEmotions.can_submit_evening;
  };

  const getPeriodIcon = () => {
    const currentPeriod = getCurrentPeriod();
    return currentPeriod === 'morning' ? (
      <Sun className="w-5 h-5 text-yellow-500" />
    ) : (
      <Moon className="w-5 h-5 text-blue-500" />
    );
  };

  const getPeriodText = () => {
    const currentPeriod = getCurrentPeriod();
    return currentPeriod === 'morning' ? 'Matin' : 'Soir';
  };

  if (isLoadingTypes) {
    return (
      <div className="card">
        <LoadingSpinner size="lg" className="py-8" />
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center space-x-2 mb-6">
        <Clock className="w-6 h-6 text-primary-600" />
        <h2 className="text-xl font-bold text-gray-900">
          Soumettre votre émotion
        </h2>
        <div className="flex items-center space-x-1 ml-auto">
          {getPeriodIcon()}
          <span className="text-sm font-medium text-gray-600">
            {getPeriodText()}
          </span>
        </div>
      </div>

      {!canSubmit() && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <p className="text-yellow-800 text-sm">
            Vous avez déjà soumis votre émotion pour cette période de la journée.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          {emotionTypes.map((emotionType) => (
            <EmotionCard
              key={emotionType.id}
              emotionType={emotionType}
              selected={selectedEmotion === emotionType.id}
              onClick={() => setSelectedEmotion(emotionType.id)}
              disabled={!canSubmit()}
            />
          ))}
        </div>

        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={() => setSelectedEmotion(null)}
            className="btn-secondary"
            disabled={isLoading || !canSubmit()}
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={!selectedEmotion || isLoading || !canSubmit()}
            className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Enregistrement...</span>
              </>
            ) : (
              <span>Enregistrer</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default EmotionSubmissionForm;