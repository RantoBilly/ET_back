import React from 'react';
import { EmotionType } from '../../types';
import EmotionIcon from './EmotionIcon';

interface EmotionCardProps {
  emotionType: EmotionType;
  selected?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}

const EmotionCard: React.FC<EmotionCardProps> = ({
  emotionType,
  selected = false,
  onClick,
  disabled = false,
}) => {
  const getEmotionColor = (name: string) => {
    switch (name.toLowerCase()) {
      case 'happy':
        return 'border-emotion-happy bg-green-50 hover:bg-green-100';
      case 'sad':
        return 'border-emotion-sad bg-gray-50 hover:bg-gray-100';
      case 'neutral':
        return 'border-emotion-neutral bg-gray-50 hover:bg-gray-100';
      case 'angry':
        return 'border-emotion-angry bg-red-50 hover:bg-red-100';
      case 'excited':
        return 'border-emotion-excited bg-purple-50 hover:bg-purple-100';
      case 'anxious':
        return 'border-emotion-anxious bg-orange-50 hover:bg-orange-100';
      default:
        return 'border-gray-300 bg-gray-50 hover:bg-gray-100';
    }
  };

  return (
    <div
      className={`
        emotion-card
        ${getEmotionColor(emotionType.name)}
        ${selected ? 'selected ring-2 ring-primary-500' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        transition-all duration-200
      `}
      onClick={disabled ? undefined : onClick}
    >
      <div className="flex flex-col items-center space-y-2">
        <div className="text-3xl">{emotionType.emoticon}</div>
        <EmotionIcon emotion={emotionType.name} size={32} />
        <div className="text-center">
          <p className="font-medium text-gray-900 capitalize">
            {emotionType.name.toLowerCase()}
          </p>
          <p className="text-sm text-gray-600">
            Degré: {emotionType.degree}
          </p>
        </div>
      </div>
    </div>
  );
};

export default EmotionCard;