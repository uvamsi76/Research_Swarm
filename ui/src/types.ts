export type AgentState = {
  id: string;
  name: string;
  state: 'idle' | 'active' | 'done' | 'conflict';
  task: string;
  progress: number;
};

export type FeedItem = {
  id: string;
  tag: string;
  text: string;
};

export type Metrics = {
  sources: number;
  claims: number;
  conflicts: number;
  verified: string;
};

export type Topic = {
  label: string;
  value: number;
};
