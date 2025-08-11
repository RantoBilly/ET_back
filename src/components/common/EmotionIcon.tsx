import React from 'react';
import { Smile, Frown, Meh, Angry, Zap, AlertTriangle } from 'lucide-react';

interface EmotionIconProps {
  emotion: string;
  size?: number;
  className?: string;
}

const EmotionIcon: React.FC<EmotionIconProps> = ({ 
  emotion, 
  size = 24, 
  className = '' 
}) => {
  const getEmotionIcon = () => {
    switch (emotion.toLowerCase()) {
      case 'happy':
        return <Smile size={size} className={`text-emotion-happy ${className}`} />;
      case 'sad':
        return <Frown size={size} className={`text-emotion-sad ${className}`} />;
      case 'neutral':
        return <Meh size={size} className={`text-emotion-neutral ${className}`} />;
      case 'angry':
        return <Angry size={size} className={`text-emotion-angry ${className}`} />;
      case 'excited':
        return <Zap size={size} className={`text-emotion-excited ${className}`} />;
      case 'anxious':
        return <AlertTriangle size={size} className={`text-emotion-anxious ${className}`} />;
      default:
        return <Meh size={size} className={`text-gray-400 ${className}`} />;
    }
  };

  return getEmotionIcon();
};

export default EmotionIcon;