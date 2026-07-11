import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('App crashed:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="kiosk mic-denied">
          <div>
            <p>Something broke: {this.state.error.message}</p>
            <p style={{ fontSize: 16, opacity: 0.7 }}>Check the browser console for details.</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
