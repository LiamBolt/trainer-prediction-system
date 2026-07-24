import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ErrorState } from '@/components/ui';

/**
 * ErrorBoundary — a top-level recoverable fallback per route (§14.4). Never a
 * blank page, never a raw error object shown to the user.
 */
interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // In production this would report to ICT RP&I; here we keep it quiet.
    if (import.meta.env.DEV) console.error('ErrorBoundary caught', error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="p-8">
          <ErrorState
            title="This section could not load"
            message="An unexpected error occurred. You can retry, or continue using the rest of the system."
            onRetry={() => this.setState({ hasError: false, error: undefined })}
          />
        </div>
      );
    }
    return this.props.children;
  }
}
