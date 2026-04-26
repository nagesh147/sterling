import React from 'react';

interface State { hasError: boolean; error: Error | null }

interface Props {
  children: React.ReactNode;
  title?: string;
}

export class PanelBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{
        background: '#141414', border: '1px solid #441111',
        borderRadius: 6, padding: 16, marginBottom: 16,
      }}>
        <div style={{ color: '#cc4444', fontSize: 11, letterSpacing: 2, marginBottom: 6 }}>
          {this.props.title ? `${this.props.title} — ERROR` : 'PANEL ERROR'}
        </div>
        <div style={{ color: '#664444', fontSize: 11, fontFamily: 'monospace' }}>
          {this.state.error?.message ?? 'Unknown render error'}
        </div>
        <button
          style={{
            marginTop: 10, background: '#1a0d0d', color: '#cc4444',
            border: '1px solid #441111', padding: '4px 10px', borderRadius: 3,
            cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
          }}
          onClick={() => this.setState({ hasError: false, error: null })}
        >
          RETRY
        </button>
      </div>
    );
  }
}
