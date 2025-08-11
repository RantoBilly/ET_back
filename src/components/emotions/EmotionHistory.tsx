import React, { useState, useEffect } from 'react';
import { Emotion } from '../../types';
import { emotionService } from '../../services/emotionService';
import EmotionIcon from '../common/EmotionIcon';
import LoadingSpinner from '../common/LoadingSpinner';
import { History, ChevronLeft, ChevronRight } from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';

const EmotionHistory: React.FC = () => {
  const [emotions, setEmotions] = useState<Emotion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const itemsPerPage = 10;

  useEffect(() => {
    loadEmotionHistory();
  }, [currentPage]);

  const loadEmotionHistory = async () => {
    try {
      setIsLoading(true);
      const response = await emotionService.getEmotionHistory({
        limit: itemsPerPage,
        offset: (currentPage - 1) * itemsPerPage,
      });
      
      setEmotions(response.results || []);
      setTotalCount(response.count || 0);
    } catch (error) {
      console.error('Error loading emotion history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const totalPages = Math.ceil(totalCount / itemsPerPage);

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  if (isLoading) {
    return (
      <div className="card">
        <LoadingSpinner size="lg" className="py-8" />
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-2">
          <History className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-bold text-gray-900">
            Historique des émotions
          </h2>
        </div>
        <span className="text-sm text-gray-500">
          {totalCount} émotion{totalCount > 1 ? 's' : ''} au total
        </span>
      </div>

      {emotions.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500">Aucune émotion enregistrée</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {emotions.map((emotion) => (
              <div
                key={emotion.id}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors duration-200"
              >
                <div className="flex items-center space-x-4">
                  <EmotionIcon emotion={emotion.emotion_type_name} size={24} />
                  <div>
                    <p className="font-medium text-gray-900 capitalize">
                      {emotion.emotion_type_name.toLowerCase()}
                    </p>
                    <p className="text-sm text-gray-600">
                      Degré: {emotion.emotion_degree}
                    </p>
                  </div>
                </div>
                
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">
                    {format(new Date(emotion.date), 'EEEE d MMMM', { locale: fr })}
                  </p>
                  <p className="text-xs text-gray-500">
                    {format(new Date(emotion.date), 'HH:mm')} - {emotion.half_day === 'morning' ? 'Matin' : 'Soir'}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
              <button
                onClick={handlePreviousPage}
                disabled={currentPage === 1}
                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Précédent</span>
              </button>
              
              <span className="text-sm text-gray-600">
                Page {currentPage} sur {totalPages}
              </span>
              
              <button
                onClick={handleNextPage}
                disabled={currentPage === totalPages}
                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>Suivant</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default EmotionHistory;