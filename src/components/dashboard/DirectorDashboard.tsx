import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { organizationService } from '../../services/organizationService';
import EmotionSummaryCard from './EmotionSummaryCard';
import LoadingSpinner from '../common/LoadingSpinner';
import { Users, TrendingUp, Calendar, Clock, Building, Download, FileText } from 'lucide-react';
import toast from 'react-hot-toast';

interface DirectorDashboardProps {
  type: 'department' | 'entity' | 'cluster' | 'drh';
}

const DirectorDashboard: React.FC<DirectorDashboardProps> = ({ type }) => {
  const { user } = useAuth();
  const [overview, setOverview] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    loadOverview();
  }, [type]);

  const loadOverview = async () => {
    try {
      let data;
      switch (type) {
        case 'department':
          data = await organizationService.getDepartmentOverview();
          break;
        case 'entity':
          data = await organizationService.getEntityOverview();
          break;
        case 'cluster':
          data = await organizationService.getClusterOverview();
          break;
        case 'drh':
          data = await organizationService.getDrhOverview();
          break;
        default:
          throw new Error('Invalid dashboard type');
      }
      setOverview(data);
    } catch (error) {
      console.error(`Error loading ${type} overview:`, error);
    } finally {
      setIsLoading(false);
    }
  };

  const downloadReport = async () => {
    try {
      setIsDownloading(true);
      let blob;
      let filename;

      switch (type) {
        case 'department':
          blob = await organizationService.getDepartmentReport('pdf');
          filename = `rapport-departement-${new Date().toISOString().split('T')[0]}.pdf`;
          break;
        case 'entity':
          blob = await organizationService.getEntityReport('pdf');
          filename = `rapport-entite-${new Date().toISOString().split('T')[0]}.pdf`;
          break;
        case 'cluster':
          blob = await organizationService.getClusterReport('pdf');
          filename = `rapport-cluster-${new Date().toISOString().split('T')[0]}.pdf`;
          break;
        case 'drh':
          blob = await organizationService.getDrhReport('pdf');
          filename = `rapport-drh-${new Date().toISOString().split('T')[0]}.pdf`;
          break;
        default:
          throw new Error('Invalid dashboard type');
      }

      organizationService.downloadReport(blob, filename);
      toast.success('Rapport téléchargé avec succès');
    } catch (error) {
      console.error('Error downloading report:', error);
      toast.error('Erreur lors du téléchargement du rapport');
    } finally {
      setIsDownloading(false);
    }
  };

  const getTitle = () => {
    switch (type) {
      case 'department':
        return 'Tableau de bord Département 🏢';
      case 'entity':
        return 'Tableau de bord Entité 🏛️';
      case 'cluster':
        return 'Tableau de bord Pôle 🌐';
      case 'drh':
        return 'Tableau de bord DRH 👥';
      default:
        return 'Tableau de bord';
    }
  };

  const getSubtitle = () => {
    switch (type) {
      case 'department':
        return 'Vue d\'ensemble des émotions de votre département';
      case 'entity':
        return 'Vue d\'ensemble des émotions de votre entité';
      case 'cluster':
        return 'Vue d\'ensemble des émotions de votre pôle';
      case 'drh':
        return 'Vue d\'ensemble globale des émotions';
      default:
        return '';
    }
  };

  const getOrganizationInfo = () => {
    switch (type) {
      case 'department':
        return user?.department_name;
      case 'entity':
        return user?.entity_name;
      case 'cluster':
        return user?.cluster_name;
      default:
        return null;
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
      <div className="bg-gradient-to-r from-indigo-600 to-indigo-700 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">{getTitle()}</h1>
            <p className="text-indigo-100">{getSubtitle()}</p>
            {getOrganizationInfo() && (
              <p className="text-indigo-200 text-sm mt-2">
                {getOrganizationInfo()}
              </p>
            )}
          </div>
          <button
            onClick={downloadReport}
            disabled={isDownloading}
            className="flex items-center space-x-2 bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg transition-colors duration-200 disabled:opacity-50"
          >
            {isDownloading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            <span>Télécharger le rapport</span>
          </button>
        </div>
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

          {/* Détails par unité organisationnelle */}
          {overview.units && overview.units.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                <Building className="w-5 h-5 text-primary-600" />
                <span>Détails par unité</span>
              </h3>
              <div className="space-y-4">
                {overview.units.map((unit: any) => (
                  <div
                    key={unit.id}
                    className="p-4 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-medium text-gray-900">{unit.name}</h4>
                      <span className="text-sm text-gray-600">
                        {unit.collaborators_count || 0} collaborateur{(unit.collaborators_count || 0) > 1 ? 's' : ''}
                      </span>
                    </div>
                    
                    {unit.emotion_summary && (
                      <div className="grid grid-cols-3 gap-4">
                        <div className="text-center">
                          <p className="text-xs text-gray-600">Aujourd'hui</p>
                          <p className="font-medium capitalize">
                            {unit.emotion_summary.today.emotion}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-600">Cette semaine</p>
                          <p className="font-medium capitalize">
                            {unit.emotion_summary.week.emotion}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-600">Ce mois</p>
                          <p className="font-medium capitalize">
                            {unit.emotion_summary.month.emotion}
                          </p>
                        </div>
                      </div>
                    )}
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

export default DirectorDashboard;