import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { PauseCircle, PlayCircle, TerminalSquare, Trash2 } from 'lucide-react';
import { useParams } from 'react-router-dom';

import Panel from '../components/ui/Panel';
import Reveal from '../components/ui/Reveal';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { useWorkloadContext } from '../context/WorkloadContext';

const API_BASE_URL = 'http://localhost:8000';

export default function DeploymentLogs() {
  const params = useParams();
  const workloadId = params.id ?? params.workload_id;
  const { setCurrentWorkloadId, wsEvents } = useWorkloadContext();
  const [lines, setLines] = useState([]);
  const [paused, setPaused] = useState(false);
  const viewportRef = useRef(null);
  const seenEventIdsRef = useRef(new Set());

  useEffect(() => {
    setCurrentWorkloadId(workloadId ?? null);
  }, [setCurrentWorkloadId, workloadId]);

  useEffect(() => {
    if (!workloadId) {
      return undefined;
    }

    let isMounted = true;

    const loadHistorical = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/results/${workloadId}/logs?limit=500`);
        if (!response.ok) {
          throw new Error(`Logs request failed: ${response.status}`);
        }
        const data = await response.json();
        if (!isMounted) {
          return;
        }

        const historicalLines = (Array.isArray(data) ? data : []).map((item) => ({
          timestamp: item.created_at,
          level: item.level ?? 'info',
          message: item.message ?? '',
        }));
        setLines(historicalLines.slice(-500));
      } catch (error) {
        console.error(error);
      }
    };

    loadHistorical();

    return () => {
      isMounted = false;
    };
  }, [workloadId]);

  useEffect(() => {
    const newest = wsEvents[0];
    if (!newest || newest.workload_id !== workloadId) {
      return;
    }

    const eventId = `${newest.event_type}-${newest.timestamp}-${newest.workload_id}`;
    if (seenEventIdsRef.current.has(eventId)) {
      return;
    }
    seenEventIdsRef.current.add(eventId);

    const mapped = mapWsEventToLog(newest);
    if (!mapped) {
      return;
    }

    setLines((current) => {
      if (current.some((item) => item.message === mapped.message)) {
        return current;
      }
      const next = [...current, mapped];
      if (next.length > 500) {
        return next.slice(100);
      }
      return next;
    });
  }, [workloadId, wsEvents]);

  useEffect(() => {
    if (paused || !viewportRef.current) {
      return;
    }
    viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
  }, [lines, paused]);

  const rendered = useMemo(
    () =>
      lines.map((line, index) => ({
        key: `${line.timestamp}-${line.message}-${index}`,
        time: toClock(line.timestamp),
        level: String(line.level ?? 'info').toLowerCase(),
        message: line.message,
      })),
    [lines],
  );

  return (
    <section className="space-y-6">
      <Reveal>
        <Panel className="p-8 sm:p-10">
          <SectionHeader
            eyebrow="Runtime evidence"
            title="Deployment log stream"
            description="Trace every AI scoring event, deployment handoff, and pod phase transition in a terminal-inspired view designed for demos and operator reviews alike."
            actions={<StatusBadge value={paused ? 'reconnecting' : 'connected'} />}
          />
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button className="control-button" onClick={() => setPaused((current) => !current)} type="button">
              {paused ? <PlayCircle size={16} /> : <PauseCircle size={16} />}
              {paused ? 'Resume autoscroll' : 'Pause autoscroll'}
            </button>
            <button className="control-button" onClick={() => setLines([])} type="button">
              <Trash2 size={16} />
              Clear stream
            </button>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs uppercase tracking-[0.24em] text-slate-400">
              <TerminalSquare size={14} />
              {rendered.length} log lines
            </div>
          </div>
        </Panel>
      </Reveal>

      <Reveal delay={0.08}>
        <Panel className="p-3 sm:p-4">
          <div
            ref={viewportRef}
            className="terminal-shell h-[560px] overflow-y-auto rounded-[24px] border border-white/10 bg-[#040814] p-4 font-mono text-[13px] leading-7 text-slate-100"
          >
            {rendered.map((line, index) => (
              <motion.div
                key={line.key}
                className="grid gap-3 border-b border-white/[0.04] px-2 py-2 last:border-none md:grid-cols-[90px_88px_1fr]"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.18, delay: Math.min(index * 0.01, 0.15) }}
              >
                <span className="text-slate-500">[{line.time}]</span>
                <span className={`font-semibold uppercase tracking-[0.2em] ${levelTone(line.level)}`}>{line.level}</span>
                <span className="text-slate-200">{line.message}</span>
              </motion.div>
            ))}
          </div>
        </Panel>
      </Reveal>
    </section>
  );
}

function mapWsEventToLog(event) {
  const timestamp = event.timestamp ?? new Date().toISOString();
  const payload = event.payload ?? {};

  switch (event.event_type) {
    case 'SCENARIO_GENERATED':
      return {
        timestamp,
        level: 'info',
        message: `Generated ${(payload.scenarios ?? []).length} scenarios for ${event.workload_id}`,
      };
    case 'AGENT_SCORED':
      return {
        timestamp,
        level: 'info',
        message: `${payload.agent}: ${payload.scenario_id} scored ${Number(payload.score ?? 0).toFixed(2)}/100 — ${payload.reasoning}`,
      };
    case 'DECISION_MADE': {
      const selectedId = payload.selected_scenario_id;
      const score = Number(payload.final_scores?.[selectedId] ?? 0).toFixed(2);
      return {
        timestamp,
        level: 'info',
        message: `Decision: ${selectedId} selected (score: ${score})`,
      };
    }
    case 'DEPLOYMENT_STARTED':
      return { timestamp, level: 'info', message: `Deploying to ${payload.node}...` };
    case 'DEPLOYMENT_SUCCESS':
      return { timestamp, level: 'info', message: `Pod ${payload.pod_name} running on ${payload.node}` };
    case 'DEPLOYMENT_FAILED':
      return { timestamp, level: 'error', message: `Deployment failed: ${payload.error}` };
    case 'POD_STATUS_UPDATE':
      return { timestamp, level: 'info', message: `Pod ${payload.pod_name}: ${payload.phase}` };
    case 'LOG_LINE':
      return { timestamp, level: payload.level ?? 'info', message: payload.message ?? '' };
    default:
      return null;
  }
}

function levelTone(level) {
  if (level === 'error') return 'text-rose-300';
  if (level === 'warn') return 'text-amber-300';
  return 'text-sky-300';
}

function toClock(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--:--:--';
  }
  return date.toLocaleTimeString(undefined, { hour12: false });
}
