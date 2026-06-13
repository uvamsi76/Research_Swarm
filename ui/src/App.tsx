import { useEffect, useMemo, useRef, useState } from 'react';
import Home from './Home';
import Dashboard from './Dashboard';
import type { AgentState, FeedItem, Metrics, Topic } from './types';

const initialAgents: Record<string, AgentState> = {
  orchestrator: {
    id: 'orchestrator',
    name: 'Orchestrator',
    state: 'idle',
    task: 'Waiting to start',
    progress: 0
  },
  web: {
    id: 'web',
    name: 'Web retriever',
    state: 'idle',
    task: '—',
    progress: 0
  },
  domain: {
    id: 'domain',
    name: 'Domain expert',
    state: 'idle',
    task: '—',
    progress: 0
  },
  financial: {
    id: 'financial',
    name: 'Financial analyst',
    state: 'idle',
    task: '—',
    progress: 0
  },
  legal: {
    id: 'legal',
    name: 'Legal analyst',
    state: 'idle',
    task: '—',
    progress: 0
  },
  devil: {
    id: 'devil',
    name: "Devil's advocate",
    state: 'idle',
    task: '—',
    progress: 0
  },
  validator: {
    id: 'validator',
    name: 'Citation validator',
    state: 'idle',
    task: '—',
    progress: 0
  },
  synthesis: {
    id: 'synthesis',
    name: 'Synthesis agent',
    state: 'idle',
    task: '—',
    progress: 0
  }
};

const initialMetrics: Metrics = {
  sources: 0,
  claims: 0,
  conflicts: 0,
  verified: '0%'
};

const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || 'http://0.0.0.0:8000').replace(/\/$/, '');

const initialTopics: Topic[] = [
  { label: 'Market size', value: 0 },
  { label: 'Regulation', value: 0 },
  { label: 'Competition', value: 0 },
  { label: 'Tech risk', value: 0 },
  { label: 'Deal flow', value: 0 }
];

const agentOrder = ['orchestrator', 'web', 'domain', 'financial', 'legal', 'devil', 'validator', 'synthesis'];

function App() {
  const [query, setQuery] = useState(
    'Should a Series B fund invest in Sarvam AI ?'
  );
  const [status, setStatus] = useState('idle');
  const [running, setRunning] = useState(false);
  const [agents, setAgents] = useState(initialAgents);
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [metrics, setMetrics] = useState<Metrics>(initialMetrics);
  const [topics, setTopics] = useState<Topic[]>(initialTopics);
  const [confidence, setConfidence] = useState(0);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportReady, setReportReady] = useState(false);
  const [activePage, setActivePage] = useState<'home' | 'dashboard'>('home');
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const resetRunState = () => {
    setAgents(initialAgents);
    setFeedItems([]);
    setMetrics(initialMetrics);
    setTopics(initialTopics);
    setConfidence(0);
    setReportReady(false);
    setStatus('running');
  };

  const updateAgent = (payload: Partial<AgentState> & { id: string }) => {
    setAgents((prev) => {
      const existing = prev[payload.id];
      if (!existing) return prev;
      return {
        ...prev,
        [payload.id]: {
          ...existing,
          state: payload.state ?? existing.state,
          task: payload.task ?? existing.task,
          progress: payload.progress ?? existing.progress
        }
      };
    });
  };

  const addFinding = (tag: string, text: string) => {
    setFeedItems((prev) => [
      ...prev,
      {
        id: `finding-${prev.length + 1}`,
        tag,
        text
      }
    ]);
  };

  const updateMetric = (payload: { id: keyof Metrics; value: number | string }) => {
    setMetrics((prev) => ({ ...prev, [payload.id]: payload.value }));
  };

  const updateTopic = (payload: { index: number; value: number }) => {
    setTopics((prev) => prev.map((topic, idx) => (idx === payload.index ? { ...topic, value: payload.value } : topic)));
  };

  const normalizeAgentId = (node: string) => {
    if (node === 'devils_advocate') return 'devil';
    return node.replace(/_agent$/, '');
  };

  const handleSsePayload = (event: { type: string; payload: any }) => {
    switch (event.type) {
      case 'agent':
        updateAgent(event.payload);
        break;
      case 'stage': {
        const id = normalizeAgentId(event.payload.stage || '');
        if (!id) break;
        updateAgent({
          id,
          state: event.payload.progress >= 100 ? 'done' : 'active',
          task: event.payload.updates?.task || event.payload.updates?.detail || `${id} in progress`,
          progress: event.payload.progress ?? 0,
        });
        break;
      }
      case 'progress': {
        const id = normalizeAgentId(event.payload.node || '');
        if (!id) break;
        updateAgent({
          id,
          state: event.payload.progress >= 100 ? 'done' : 'active',
          task: event.payload.detail || `${id} in progress`,
          progress: event.payload.progress ?? 0,
        });
        break;
      }
      case 'finding':
        addFinding(event.payload.tag, event.payload.text);
        break;
      case 'metric':
        updateMetric(event.payload);
        break;
      case 'topic':
        updateTopic(event.payload);
        break;
      case 'confidence':
        setConfidence(event.payload.value);
        break;
      case 'status':
        setStatus(event.payload.status);
        break;
      case 'report':
        setReportReady(event.payload.status === 'ready');
        break;
      case 'error':
        setStatus('error');
        setRunning(false);
        break;
      case 'complete':
        setRunning(false);
        sourceRef.current?.close();
        sourceRef.current = null;
        break;
      default:
        break;
    }
  };

  const downloadReport = async () => {
    if (reportLoading) return;
    setReportError(null);
    setReportLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/report?query=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error(`Report failed: ${response.statusText}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'researchswarm-report.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setReportError(error instanceof Error ? error.message : 'Unable to download report');
    } finally {
      setReportLoading(false);
    }
  };

  const startSse = () => {
    sourceRef.current?.close();
    const url = `${BACKEND_URL}/api/query/stream?query=${encodeURIComponent(query)}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    const eventNames = ['agent', 'stage', 'progress', 'finding', 'metric', 'topic', 'confidence', 'status', 'report', 'error', 'complete'];

    eventNames.forEach((eventName) => {
      source.addEventListener(eventName, (event) => {
        try {
          const payload = JSON.parse((event as MessageEvent).data);
          handleSsePayload({ type: eventName, payload });
        } catch (error) {
          console.error('Invalid SSE payload:', error);
        }
      });
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        setStatus('error');
        setRunning(false);
      }
    };
  };

  const startRun = () => {
    if (running) return;
    resetRunState();
    setRunning(true);
    startSse();
  };

  return (
    <div className="app app-shell">
      <div className={`page-shell ${activePage === 'home' ? 'page-visible' : 'page-hidden'}`}>
        <Home query={query} onQueryChange={setQuery} onStart={() => {
          setActivePage('dashboard');
          startRun();
        }} />
      </div>

      <div className={`page-shell ${activePage === 'dashboard' ? 'page-visible' : 'page-hidden'}`}>
        <Dashboard
          query={query}
          setQuery={setQuery}
          status={status}
          running={running}
          agents={agents}
          feedItems={feedItems}
          metrics={metrics}
          topics={topics}
          confidence={confidence}
          reportLoading={reportLoading}
          reportError={reportError}
          reportReady={reportReady}
          startRun={startRun}
          downloadReport={downloadReport}
        />
      </div>
    </div>
  );
}

export default App;
