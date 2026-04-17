import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { useWorkloadWS } from '../hooks/useWorkloadWS';

const API_BASE_URL = 'http://localhost:8000';
const POLL_INTERVAL_MS = 10000;
const REQUEST_TIMEOUT_MS = 8000;

const WorkloadContext = createContext(null);

async function fetchDecisionBundle(workloadId) {
  if (!workloadId) return null;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/results/${workloadId}/decision-panel`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Decision bundle request failed: ${response.status}`);
    }

    const payload = await response.json();
    if (!payload?.decision) return null;

    return {
      ...payload.decision,
      all_scenarios: Array.isArray(payload.scenarios) ? payload.scenarios : [],
      agent_scores: Array.isArray(payload.scores) ? payload.scores : [],
    };
  } finally {
    window.clearTimeout(timeout);
  }
}

export function WorkloadProvider({ children }) {
  const [currentWorkloadId, setCurrentWorkloadId] = useState(null);
  const [latestDecision, setLatestDecision] = useState(null);
  const [clusterNodes, setClusterNodes] = useState([]);
  const { events: wsEvents, status: wsStatus } = useWorkloadWS(currentWorkloadId);
  const lastDecisionEventRef = useRef(null);

  const refreshClusterNodes = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/metrics/nodes`);
      if (!response.ok) throw new Error(`Metrics request failed: ${response.status}`);
      const data = await response.json();
      setClusterNodes(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to fetch live node metrics', error);
    }
  }, []);

  const refreshDecision = useCallback(async (workloadId) => {
    try {
      const decision = await fetchDecisionBundle(workloadId);
      setLatestDecision(decision);
    } catch (error) {
      console.error('Failed to fetch decision bundle', error);
    }
  }, []);

  useEffect(() => {
    refreshClusterNodes();
    const intervalId = window.setInterval(refreshClusterNodes, POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [refreshClusterNodes]);

  useEffect(() => {
    if (!currentWorkloadId) {
      setLatestDecision(null);
      return;
    }
    refreshDecision(currentWorkloadId);
  }, [currentWorkloadId, refreshDecision]);

  useEffect(() => {
    const newestEvent = wsEvents[0];
    if (!newestEvent || newestEvent.event_type !== 'DECISION_MADE') return;
    if (lastDecisionEventRef.current === newestEvent.timestamp) return;
    lastDecisionEventRef.current = newestEvent.timestamp;
    refreshDecision(newestEvent.workload_id);
  }, [wsEvents, refreshDecision]);

  // Supabase realtime channel intentionally removed. Decision updates are
  // handled via local backend websocket events and explicit refresh calls.

  const value = useMemo(
    () => ({
      currentWorkloadId,
      latestDecision,
      clusterNodes,
      wsStatus,
      wsEvents,
      setCurrentWorkloadId,
      refreshDecision,
      refreshClusterNodes,
    }),
    [clusterNodes, currentWorkloadId, latestDecision, refreshClusterNodes, refreshDecision, wsEvents, wsStatus],
  );

  return <WorkloadContext.Provider value={value}>{children}</WorkloadContext.Provider>;
}

export function useWorkloadContext() {
  const context = useContext(WorkloadContext);
  if (!context) throw new Error('useWorkloadContext must be used within WorkloadProvider');
  return context;
}