# AI Model settings editor

Settings → AI Model → Default models & connection supports OpenAI, Google Gemini,
Anthropic, OpenRouter, xAI and OpenAI-compatible Custom/Ollama/vLLM providers.

- Enter default/fallback model names supported by the selected provider. Both
  models use the selected provider and its key. Google uses the standard endpoint;
  this editor does not support a custom Google URL or Vertex ADC configuration.
- API key is write-only. A blank field preserves the existing key. Changing provider
  clears the unsaved key and URLs to avoid sending credentials to the wrong service.
- Base URL includes the API prefix. Blank fallback URL uses the primary Base URL.
  The provider's default endpoint is used when no custom URL is set. Only configure
  trusted endpoints: both models use the same credential.
- Save & restart opens a warning/confirmation before writing files or restarting.
  Busy tasks, queue, paused runs, in-flight email or an existing shutdown block Save.
- On confirmation, update the `default` object in `artemis.jsonc` and the selected
  provider's credential variables in `.env`. Unrelated config, nodes, presets and
  dotenv entries are preserved. Comments inside the rewritten default object are
  replaced by formatted JSON; comments outside it remain.
- Per-agent overrides, including the Flash step summarizer, are NOT changed.
  They may continue using explicitly configured providers/models.
- Reload is required if file versions changed since the form was loaded. If a
  write fails, the previous dotenv text is restored. Keep normal file backups:
  two-file updates cannot guarantee an atomic transaction through OS/power failure.
- The restart helper waits for the old process to exit before starting the new
  daemon on the same host/port. Old inherited values of updated env variables are
  removed so startup reloads `.env`. No keys are placed in process arguments.
- The page polls for a different server PID, reloads settings after recovery, and
  reports a timeout instead of falsely claiming success. Restart helper logs go
  to the usual daemon log. If spawning fails, files remain saved and the UI asks
  for a manual restart.

After installing this backend feature, restart ARTEMIS once, then refresh the
Web UI. Subsequent Save & restart operations are automatic after confirmation.
External MCP hosts retaining old environment values may need their own restart.
