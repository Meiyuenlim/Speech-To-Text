export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="spinner" />{label}</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="error-state" role="alert"><strong>Something needs attention</strong><span>{message}</span></div>;
}
