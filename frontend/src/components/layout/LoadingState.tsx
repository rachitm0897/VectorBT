type LoadingStateProps = {
  label?: string;
};

export default function LoadingState({ label = "Loading analytics" }: LoadingStateProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {Array.from({ length: 10 }).map((_, index) => (
          <div key={index} className="h-20 animate-pulse border border-line bg-panel" />
        ))}
      </div>
      <div className="h-[460px] animate-pulse border border-line bg-panel" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="h-80 animate-pulse border border-line bg-panel" />
        <div className="h-80 animate-pulse border border-line bg-panel" />
      </div>
      <p className="text-xs uppercase tracking-[0.16em] text-muted">{label}</p>
    </div>
  );
}
