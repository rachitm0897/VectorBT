type ErrorStateProps = {
  message: string;
};

export default function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="border border-red/60 bg-red/10 p-5">
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-red">Request Failed</div>
      <p className="text-sm leading-6 text-text">{message}</p>
    </div>
  );
}
