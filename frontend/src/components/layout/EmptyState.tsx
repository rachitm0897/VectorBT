type EmptyStateProps = {
  title: string;
  message: string;
};

export default function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="flex min-h-48 items-center justify-center border border-dashed border-line bg-ink p-6 text-center">
      <div>
        <div className="text-sm font-semibold text-text">{title}</div>
        <p className="mt-2 max-w-md text-sm leading-6 text-muted">{message}</p>
      </div>
    </div>
  );
}
