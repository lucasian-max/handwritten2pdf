import type { ConversionMode } from "./types";

const STORAGE_KEY = "n2l_settings";

export interface ProviderPreset {
  id: string;
  group: string;
  label: string;
  model: string;
  apiBase: string;
}

/**
 * Ordered so the first entry is the default for this fork.
 * `model` keeps the provider prefix the backend expects.
 */
export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: "deepseek-v4.1-flash",
    group: "DeepSeek",
    label: "DeepSeek v4.1 Flash (best tested)",
    model: "openai/deepseek/deepseek-v4.1-flash",
    apiBase: "https://ai.hackclub.com/proxy/v1",
  },
  {
    id: "gemini-3-flash",
    group: "Google",
    label: "Gemini 3 Flash (fastest tested)",
    model: "openai/google/gemini-3-flash-preview",
    apiBase: "https://ai.hackclub.com/proxy/v1",
  },
  {
    id: "hackclub",
    group: "Hack Club",
    label: "Hack Club AI (GLM 5.3 Flash)",
    model: "openai/z-ai/glm-5.3-flash",
    apiBase: "https://ai.hackclub.com/proxy/v1",
  },
  {
    id: "gemini-2-5-pro",
    group: "Google",
    label: "Gemini 2.5 Pro",
    model: "openrouter/google/gemini-2.5-pro-preview",
    apiBase: "https://openrouter.ai/api/v1",
  },
  {
    id: "claude-sonnet",
    group: "Anthropic",
    label: "Claude Sonnet 4.6",
    model: "anthropic/claude-sonnet-4-6",
    // Bare domain: litellm appends "/v1/messages" itself, so a "/v1" suffix
    // here would request /v1/v1/messages.
    apiBase: "https://api.anthropic.com",
  },
  {
    id: "claude-haiku",
    group: "Anthropic",
    label: "Claude Haiku 4.5",
    model: "anthropic/claude-haiku-4-5-20251001",
    apiBase: "https://api.anthropic.com",
  },
  {
    id: "gpt-4o",
    group: "OpenAI",
    label: "GPT-4o",
    model: "openai/gpt-4o",
    apiBase: "https://api.openai.com/v1",
  },
  {
    id: "gpt-4-1-mini",
    group: "OpenAI",
    label: "GPT-4.1 Mini",
    model: "openai/gpt-4.1-mini",
    apiBase: "https://api.openai.com/v1",
  },
];

export const DEFAULT_PRESET = PROVIDER_PRESETS[0];

export interface AppSettings {
  model: string;
  customModel: string;
  useCustomModel: boolean;
  apiKey: string;
  preamble: string;
  /** True only when the user actually edited the preamble away from the
   *  server default. When false, no preamble is sent and the backend's own
   *  (kept current) default is used. */
  preambleIsCustom: boolean;
  apiBase: string;
  mode: ConversionMode;
  pipeline: "single" | "split";
}

const DEFAULTS: AppSettings = {
  model: DEFAULT_PRESET.model,
  customModel: "",
  useCustomModel: false,
  apiKey: "",
  preamble: "",
  preambleIsCustom: false,
  apiBase: DEFAULT_PRESET.apiBase,
  mode: "material",
  pipeline: "split",
};

/**
 * A stored copy of an *older default* preamble would keep the thmtools bug
 * that breaks TeX Live 2026 compilation (thmtools loaded before the
 * \newtheorem block). Detect it and treat the preamble as absent so the
 * backend ships its fixed default instead. A genuinely customized preamble
 * that happens to match this shape is rare and can simply be re-saved.
 */
function looksLikeStaleDefaultPreamble(preamble: string): boolean {
  const thmtools = preamble.indexOf("\\usepackage{thmtools}");
  const newtheorem = preamble.indexOf("\\newtheorem");
  return thmtools !== -1 && newtheorem !== -1 && thmtools < newtheorem;
}

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const stored = JSON.parse(raw) as Partial<AppSettings>;
    const storedPreamble =
      typeof stored.preamble === "string" ? stored.preamble : "";
    const stalePreamble = looksLikeStaleDefaultPreamble(storedPreamble);
    return {
      ...DEFAULTS,
      ...stored,
      // Installations saved before base URLs existed keep the server default.
      apiBase: stored.apiBase ?? "",
      mode: stored.mode === "transcribe" ? "transcribe" : "material",
      pipeline: stored.pipeline === "single" ? "single" : "split",
      preamble: stalePreamble ? "" : storedPreamble,
      preambleIsCustom: !stalePreamble && Boolean(stored.preambleIsCustom),
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings: AppSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function presetForModel(model: string): ProviderPreset | undefined {
  return PROVIDER_PRESETS.find((preset) => preset.model === model);
}

export function getEffectiveModel(settings: AppSettings): string {
  const model = settings.useCustomModel ? settings.customModel : settings.model;
  return model.trim();
}

export function getEffectiveApiBase(settings: AppSettings): string | null {
  return settings.apiBase.trim() || null;
}

export function modeLabel(mode: ConversionMode | undefined): string {
  return mode === "transcribe" ? "Faithful transcription" : "Student notes";
}
