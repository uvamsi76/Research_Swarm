import React, { useMemo } from 'react';
import { AgentState, FeedItem, Metrics, Topic } from './types';

type DashboardProps = {
  query: string;
  setQuery: (value: string) => void;
  status: string;
  running: boolean;
  agents: Record<string, AgentState>;
  feedItems: FeedItem[];
  metrics: Metrics;
  topics: Topic[];
  confidence: number;
  reportLoading: boolean;
  reportError: string | null;
  reportReady: boolean;
  startRun: () => void;
  downloadReport: () => void;
};

const agentOrder = ['orchestrator', 'web', 'domain', 'financial', 'legal', 'devil', 'validator', 'synthesis'];

function getStatusColor(state: AgentState['state']) {
  if (state === 'active') return '#5B4AE8';
  if (state === 'done') return '#22C55E';
  if (state === 'conflict') return '#F59E0B';
  return 'var(--color-border-tertiary)';
}

function getFillColor(state: AgentState['state']) {
  if (state === 'active') return 'rgba(91, 74, 232, 0.08)';
  if (state === 'done') return 'rgba(34, 197, 94, 0.07)';
  if (state === 'conflict') return 'rgba(245, 158, 11, 0.08)';
  return 'var(--color-background-secondary)';
}

export default function Dashboard({
  query,
  setQuery,
  status,
  running,
  agents,
  feedItems,
  metrics,
  topics,
  confidence,
  reportLoading,
  reportError,
  reportReady,
  startRun,
  downloadReport
}: DashboardProps) {
  const parallelState = useMemo(() => {
    const states = [agents.web.state, agents.domain.state, agents.financial.state, agents.legal.state];
    if (states.includes('conflict')) return 'conflict';
    if (states.includes('active')) return 'active';
    if (states.every((state) => state === 'done')) return 'done';
    if (states.some((state) => state === 'done')) return 'active';
    return 'idle';
  }, [agents.domain.state, agents.financial.state, agents.legal.state, agents.web.state]);

  const edgeStyles = {
    edge1: agents.orchestrator.state !== 'idle',
    edge2: agents.orchestrator.state !== 'idle',
    edge3: agents.orchestrator.state !== 'idle',
    edge4: parallelState !== 'idle',
    edge5: parallelState !== 'idle',
    edge6: parallelState !== 'idle',
    edge9: agents.orchestrator.state !== 'idle',
    edge7: agents.devil.state !== 'idle',
    edge8: agents.validator.state !== 'idle'
  };

  return (
    <div className="app">
      <div className="topbar">
        <div className="logo">
          Research<span>Swarm</span>
        </div>
        <input
          className="query-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Enter your research query"
        />
        <div className="status-badge">
          <div
            className="pulse-dot"
            style={{
              background: status === 'running' ? '#22c55e' : status === 'done' ? '#22c55e' : '#888'
            }}
          />
          <span>{status}</span>
        </div>
      </div>

      <div className="main">
        <div className="left-panel">
          <div className="panel-label">Agent swarm</div>
          {agentOrder.map((agentId) => {
            const agent = agents[agentId];
            return (
              <div key={agent.id} className={`agent-card ${agent.state}`}>
                <div className="agent-header">
                  <div className="agent-name">{agent.name}</div>
                  <div className="agent-status-dot" />
                </div>
                <div className="agent-task">{agent.task}</div>
                <div className="agent-progress">
                  <div className="agent-progress-bar" style={{ width: `${agent.progress}%` }} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="center-panel">
          <div className="panel-label">Orchestration flow</div>
          <div className="flow-graph">
            <svg className="graph-svg-wrap" viewBox="0 0 480 140" role="img">
              <title>Live orchestration flow graph</title>
              <defs>
                <marker
                  id="ga"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path
                    d="M2 1L8 5L2 9"
                    fill="none"
                    stroke="context-stroke"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </marker>
              </defs>
              <g id="gn-orchestrator">
                <rect
                  x="8"
                  y="36"
                  width="88"
                  height="36"
                  rx="6"
                  fill={getFillColor(agents.orchestrator.state)}
                  stroke={getStatusColor(agents.orchestrator.state)}
                  strokeWidth="0.8"
                />
                <text x="52" y="57" textAnchor="middle" fontSize="10" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.orchestrator.state)}>
                  Orchestrator
                </text>
              </g>
              <g id="gn-parallel">
                <rect
                  x="120"
                  y="8"
                  width="74"
                  height="28"
                  rx="5"
                  fill={getFillColor(parallelState)}
                  stroke={parallelState === 'idle' ? 'var(--color-border-tertiary)' : getStatusColor(parallelState)}
                  strokeWidth="0.6"
                />
                <text x="157" y="25" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={parallelState === 'idle' ? 'var(--color-text-tertiary)' : getStatusColor(parallelState)}>
                  Web ret.
                </text>
                <rect
                  x="120"
                  y="42"
                  width="74"
                  height="28"
                  rx="5"
                  fill={getFillColor(parallelState)}
                  stroke={parallelState === 'idle' ? 'var(--color-border-tertiary)' : getStatusColor(parallelState)}
                  strokeWidth="0.6"
                />
                <text x="157" y="59" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={parallelState === 'idle' ? 'var(--color-text-tertiary)' : getStatusColor(parallelState)}>
                  Domain
                </text>
                <rect
                  x="120"
                  y="76"
                  width="74"
                  height="28"
                  rx="5"
                  fill={getFillColor(parallelState)}
                  stroke={parallelState === 'idle' ? 'var(--color-border-tertiary)' : getStatusColor(parallelState)}
                  strokeWidth="0.6"
                />
                <text x="157" y="93" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={parallelState === 'idle' ? 'var(--color-text-tertiary)' : getStatusColor(parallelState)}>
                  Financial
                </text>
                <rect
                  x="120"
                  y="110"
                  width="74"
                  height="28"
                  rx="5"
                  fill={getFillColor(parallelState)}
                  stroke={parallelState === 'idle' ? 'var(--color-border-tertiary)' : getStatusColor(parallelState)}
                  strokeWidth="0.6"
                />
                <text x="157" y="127" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={parallelState === 'idle' ? 'var(--color-text-tertiary)' : getStatusColor(parallelState)}>
                  Legal
                </text>
              </g>
              <g id="gn-devil">
                <rect
                  x="218"
                  y="36"
                  width="68"
                  height="36"
                  rx="6"
                  fill={getFillColor(agents.devil.state)}
                  stroke={getStatusColor(agents.devil.state)}
                  strokeWidth="0.6"
                />
                <text x="252" y="52" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.devil.state)}>
                  Devil's
                </text>
                <text x="252" y="64" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.devil.state)}>
                  adv.
                </text>
              </g>
              <g id="gn-validator">
                <rect
                  x="308"
                  y="36"
                  width="68"
                  height="36"
                  rx="6"
                  fill={getFillColor(agents.validator.state)}
                  stroke={getStatusColor(agents.validator.state)}
                  strokeWidth="0.6"
                />
                <text x="342" y="52" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.validator.state)}>
                  Validator
                </text>
              </g>
              <g id="gn-synthesis">
                <rect
                  x="398"
                  y="36"
                  width="74"
                  height="36"
                  rx="6"
                  fill={getFillColor(agents.synthesis.state)}
                  stroke={getStatusColor(agents.synthesis.state)}
                  strokeWidth="0.6"
                />
                <text x="435" y="52" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.synthesis.state)}>
                  Synthesis
                </text>
                <text x="435" y="64" textAnchor="middle" fontSize="9" fontFamily="IBM Plex Mono,monospace" fill={getStatusColor(agents.synthesis.state)}>
                  + report
                </text>
              </g>
              <line
                x1="96"
                y1="54"
                x2="118"
                y2="22"
                stroke={edgeStyles.edge1 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge1 ? 0.8 : 0.3}
              />
              <line
                x1="96"
                y1="54"
                x2="118"
                y2="56"
                stroke={edgeStyles.edge2 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge2 ? 0.8 : 0.3}
              />
              <line
                x1="96"
                y1="54"
                x2="118"
                y2="90"
                stroke={edgeStyles.edge3 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge3 ? 0.8 : 0.3}
              />
              <line
                x1="96"
                y1="54"
                x2="118"
                y2="124"
                stroke={edgeStyles.edge9 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge9 ? 0.8 : 0.3}
              />
              <line
                x1="194"
                y1="22"
                x2="216"
                y2="46"
                stroke={edgeStyles.edge4 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge4 ? 0.8 : 0.3}
              />
              <line
                x1="194"
                y1="56"
                x2="216"
                y2="54"
                stroke={edgeStyles.edge5 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge5 ? 0.8 : 0.3}
              />
              <line
                x1="194"
                y1="90"
                x2="216"
                y2="62"
                stroke={edgeStyles.edge6 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge6 ? 0.8 : 0.3}
              />
              <line
                x1="286"
                y1="54"
                x2="306"
                y2="54"
                stroke={edgeStyles.edge7 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge7 ? 0.8 : 0.3}
              />
              <line
                x1="376"
                y1="54"
                x2="396"
                y2="54"
                stroke={edgeStyles.edge8 ? '#5B4AE8' : 'var(--color-border-tertiary)'}
                strokeWidth="0.7"
                markerEnd="url(#ga)"
                opacity={edgeStyles.edge8 ? 0.8 : 0.3}
              />
            </svg>
          </div>

          <div className="findings-feed">
            <div className="feed-header">
              <div className="feed-header-title">Live findings stream</div>
              <div className="feed-count">{feedItems.length} finding{feedItems.length !== 1 ? 's' : ''}</div>
            </div>
            <div className="feed-body">
              {feedItems.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'IBM Plex Mono, monospace', padding: '10px 4px' }}>
                  Waiting for agents to start...
                </div>
              ) : (
                feedItems.map((item) => (
                  <div key={item.id} className="finding-item">
                    <span className={`finding-tag ${item.tag}`}>{item.tag}</span>
                    <span className="finding-text">{item.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="right-panel">
          <div className="panel-label">Run metrics</div>
          <div className="metrics-grid">
            <div className="metric-box">
              <div className="metric-val">{metrics.sources}</div>
              <div className="metric-label">Sources</div>
            </div>
            <div className="metric-box">
              <div className="metric-val">{metrics.claims}</div>
              <div className="metric-label">Claims</div>
            </div>
            <div className="metric-box">
              <div className="metric-val">{metrics.conflicts}</div>
              <div className="metric-label">Conflicts</div>
            </div>
            <div className="metric-box">
              <div className="metric-val">{metrics.verified}</div>
              <div className="metric-label">Verified</div>
            </div>
          </div>

          <div className="section-divider" />
          <div className="panel-label" style={{ marginBottom: 10 }}>
            Topic coverage
          </div>
          {topics.map((topic) => (
            <div className="topic-item" key={topic.label}>
              <div className="topic-label">{topic.label}</div>
              <div className="topic-bar-wrap">
                <div className="topic-bar" style={{ width: `${topic.value}%` }} />
              </div>
            </div>
          ))}

          <div className="section-divider" />
          <div className="panel-label" style={{ marginBottom: 10 }}>
            Overall confidence
          </div>

          <div className="confidence-ring-wrap">
            <svg width="80" height="80" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="30" fill="none" stroke="var(--color-border-tertiary)" strokeWidth="6" />
              <circle
                cx="40"
                cy="40"
                r="30"
                fill="none"
                stroke="#5B4AE8"
                strokeWidth="6"
                strokeDasharray="188.5"
                strokeDashoffset={188.5 - (188.5 * confidence) / 100}
                strokeLinecap="round"
                transform="rotate(-90 40 40)"
                style={{ transition: 'stroke-dashoffset 1s ease' }}
              />
              <text x="40" y="44" textAnchor="middle" fontSize="14" fontFamily="IBM Plex Mono,monospace" fill="var(--color-text-primary)" fontWeight="500">
                {confidence}%
              </text>
            </svg>
            <div className="conf-label">Confidence</div>
          </div>

          <button className="run-btn" onClick={startRun} disabled={running}>
            {running ? 'Running…' : status === 'done' ? '↺ Run again' : '▶ Run swarm'}
          </button>
          {status === 'done' && (
            <button
              className="run-btn"
              onClick={downloadReport}
              disabled={reportLoading}
              style={{ marginTop: 10, background: '#22C55E' }}
            >
              {reportLoading ? 'Preparing PDF…' : 'Download full report PDF'}
            </button>
          )}
          {reportReady && !reportLoading && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#22C55E' }}>
              PDF report generated and ready for download.
            </div>
          )}
          {reportError && (
            <div style={{ marginTop: 10, fontSize: 11, color: '#f87171' }}>{reportError}</div>
          )}
          <div className="sse-note">Updates via SSE — server-driven progress</div>
        </div>
      </div>
    </div>
  );
}
