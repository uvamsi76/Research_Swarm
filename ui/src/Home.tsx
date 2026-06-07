import React from 'react';

type HomeProps = {
  query: string;
  onQueryChange: (value: string) => void;
  onStart: () => void;
};

export default function Home({ query, onQueryChange, onStart }: HomeProps) {
  return (
    <div className="page home-page">
      <div className="home-shell">
        <div className="home-tag">Connect your AI agents to the web</div>
        <h1 className="home-title">Research faster with live agent orchestration.</h1>
        <p className="home-copy">
          Enter a research question and launch the dashboard to see a coordinated swarm of agents gather, verify, and summarize insights in real time.
        </p>

        <div className="home-action-row">
          <input
            className="home-query-input"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="What should the agents research today?"
          />
          <button className="home-start-btn" onClick={onStart}>
            Start research
          </button>
        </div>

        <div className="home-help-text">
          Smooth transition into the dashboard, with search powered by your query and the live swarm interface ready to run.
        </div>
      </div>
    </div>
  );
}
