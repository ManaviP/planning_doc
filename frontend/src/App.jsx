import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import AppShell from './components/layout/AppShell';
import { WorkloadProvider } from './context/WorkloadContext';

const AIDecisionPanel = lazy(() => import('./pages/AIDecisionPanel'));
const ClusterOverview = lazy(() => import('./pages/ClusterOverview'));
const DashboardHome = lazy(() => import('./pages/DashboardHome'));
const DeploymentLogs = lazy(() => import('./pages/DeploymentLogs'));
const ModelEvaluation = lazy(() => import('./pages/ModelEvaluation'));
const NodeTopology = lazy(() => import('./pages/NodeTopology'));
const ParetoGraphPage = lazy(() => import('./pages/ParetoGraph'));
const PreviewControlPlane = lazy(() => import('./pages/PreviewControlPlane'));
const WorkloadForm = lazy(() => import('./pages/WorkloadForm'));

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <WorkloadProvider>
        <AppShell>
          <Suspense fallback={<RouteSkeleton />}>
            <Routes>
              <Route element={<DashboardHome />} path="/" />
              <Route element={<WorkloadForm />} path="/workloads" />
              <Route element={<ClusterOverview />} path="/cluster" />
              <Route element={<NodeTopology />} path="/topology" />
              <Route element={<AIDecisionPanel />} path="/decision" />
              <Route element={<AIDecisionPanel />} path="/decision/:id" />
              <Route element={<PreviewControlPlane />} path="/preview" />
              <Route element={<ModelEvaluation />} path="/evaluation/:id" />
              <Route element={<ParetoGraphPage />} path="/pareto/:id" />
              <Route element={<DeploymentLogs />} path="/logs/:id" />
              <Route element={<Navigate replace to="/" />} path="*" />
            </Routes>
          </Suspense>
        </AppShell>
      </WorkloadProvider>
    </BrowserRouter>
  );
}

function RouteSkeleton() {
  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="shimmer h-36 rounded-[28px] border border-white/10 bg-white/5" />
      ))}
    </div>
  );
}
