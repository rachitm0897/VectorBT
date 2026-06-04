import { DEFAULT_CHAT_MODEL, DEFAULT_CHAT_URL, type ApiKeys } from "../api/client";


type ApiKeyPanelProps = {
  apiKeys: ApiKeys;
  onChange: (apiKeys: ApiKeys) => void;
};


export default function ApiKeyPanel({ apiKeys, onChange }: ApiKeyPanelProps) {
  const hasChatKey = apiKeys.chatApiKey.trim().length > 0;
  const hasChatUrl = (apiKeys.chatUrl.trim() || DEFAULT_CHAT_URL).length > 0;
  const hasModel = (apiKeys.model.trim() || DEFAULT_CHAT_MODEL).length > 0;
  const hasFinnhub = apiKeys.finnhubApiKey.trim().length > 0;
  const isReady = hasChatKey && hasChatUrl && hasModel && hasFinnhub;

  function updateKey(name: keyof ApiKeys, value: string) {
    onChange({ ...apiKeys, [name]: value });
  }

  function resetConfig() {
    onChange({ chatUrl: DEFAULT_CHAT_URL, chatApiKey: "", model: DEFAULT_CHAT_MODEL, finnhubApiKey: "" });
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between border border-line bg-ink px-3 py-2">
        <span className="text-xs leading-5 text-muted">Use an OpenAI-compatible chat endpoint. Default URL is OpenAI.</span>
        <span
          className={`ml-3 shrink-0 border px-2 py-1 text-[11px] uppercase tracking-[0.14em] ${
            isReady ? "border-green/60 text-green" : "border-red/60 text-red"
          }`}
        >
          {isReady ? "Ready" : "Missing"}
        </span>
      </div>

      <label className="space-y-2">
        <span className="form-label">Chat URL</span>
        <input
          className="form-control font-mono text-xs"
          value={apiKeys.chatUrl}
          onChange={(event) => updateKey("chatUrl", event.target.value)}
          placeholder={DEFAULT_CHAT_URL}
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label className="space-y-2">
        <span className="form-label">Chat API Key</span>
        <input
          className="form-control font-mono text-xs"
          type="password"
          value={apiKeys.chatApiKey}
          onChange={(event) => updateKey("chatApiKey", event.target.value)}
          placeholder="Provider key"
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label className="space-y-2">
        <span className="form-label">Model</span>
        <input
          className="form-control font-mono text-xs"
          value={apiKeys.model}
          onChange={(event) => updateKey("model", event.target.value)}
          placeholder={DEFAULT_CHAT_MODEL}
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label className="space-y-2">
        <span className="form-label">Finnhub API Key</span>
        <input
          className="form-control font-mono text-xs"
          type="password"
          value={apiKeys.finnhubApiKey}
          onChange={(event) => updateKey("finnhubApiKey", event.target.value)}
          placeholder="Finnhub token"
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <button
        className="w-full border border-line bg-ink px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted transition hover:border-red hover:text-red"
        type="button"
        onClick={resetConfig}
      >
        Reset Config
      </button>
    </div>
  );
}
