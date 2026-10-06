import React, { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div dir="rtl" className="flex h-screen w-screen flex-col items-center justify-center bg-bg-primary p-6 text-center text-text-primary">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-accent-red/20 text-3xl text-accent-red">
            ⚠️
          </div>
          <h1 className="mb-2 text-xl font-bold">متأسفانه مشکلی پیش آمد</h1>
          <p className="mb-8 text-sm text-text-secondary">
            خطایی در نمایش این بخش رخ داد. تلاش مجدد ممکن است مشکل را برطرف کند.
          </p>
          <button
            onClick={this.handleRetry}
            className="rounded-lg bg-accent-blue px-6 py-2.5 text-sm font-bold text-bg-primary transition-opacity hover:opacity-90"
          >
            تلاش مجدد و بارگذاری
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
