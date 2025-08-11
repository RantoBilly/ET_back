import React from 'react';
import { EmotionSummary } from '../../types';
import EmotionIcon from '../common/EmotionIcon';

interface EmotionSummaryCardProps {
  title: string;
  summary: EmotionSummary;
  icon: React.ReactNode;
  className?: string;
}

const EmotionSummaryCard: React.FC<EmotionSummaryCardProps> = ({
  title,
  summary,
  icon,
  className = '',
}) => {
  const getEmotionColor = (emotion: string) => {
    switch (emotion.toLowerCase()) {
      case 'happy':
        return 'bg-green-50 border-green-200';
      case 'sad':
        return 'bg-gray-50 border-gray-200';
      case 'neutral':
        return 'bg-gray-50 border-gray-200';
      case 'angry':
        return 'bg-red-50 border-red-200';
      case 'excited':
        return 'bg-purple-50 border-purple-200';
      case 'anxious':
        return 'bg-orange-50 border-orange-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className={`card ${getEmotionColor(summary.emotion)} ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          {icon}
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        </div>
        <EmotionIcon emotion={summary.emotion} size={32} />
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Émotion dominante:</span>
          <span className="font-medium text-gray-900 capitalize">
            {summary.emotion}
          </span>
        </div>
        
        {summary.average_degree !== null && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Degré moyen:</span>
            <span className="font-medium text-gray-900">
              {summary.average_degree.toFixed(1)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmotionSummaryCard;