import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import Layout from '../components/layout/Layout';
import EmployeeDashboard from '../components/dashboard/EmployeeDashboard';
import ManagerDashboard from '../components/dashboard/ManagerDashboard';
import DirectorDashboard from '../components/dashboard/DirectorDashboard';

const Dashboard: React.FC = () => {
  const { user } = useAuth();

  const renderDashboard = () => {
    if (!user) return null;

    switch (user.role) {
      case 'employee':
        return <EmployeeDashboard />;
      case 'manager':
        return <ManagerDashboard />;
      case 'department_director':
        return <DirectorDashboard type="department" />;
      case 'entity_director':
        return <DirectorDashboard type="entity" />;
      case 'pole_director':
        return <DirectorDashboard type="cluster" />;
      case 'admin':
        return <DirectorDashboard type="drh" />;
      default:
        return <EmployeeDashboard />;
    }
  };

  return (
    <Layout>
      {renderDashboard()}
    </Layout>
  );
};

export default Dashboard;