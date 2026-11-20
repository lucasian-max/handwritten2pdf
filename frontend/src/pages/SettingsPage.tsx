import { useState, useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ExternalLink, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  PROVIDER_PRESETS,
  loadSettings,
  saveSettings,
  presetForModel,
  type AppSettings,
  type ProviderPreset,
} from "@/lib/settings";
import { fetchDefaultPreamble } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ConversionMode } from "@/lib/types";

const PRESET_GROUPS = PROVIDER_PRESETS.reduce<
  { group: string; presets: ProviderPreset[] }[]
>((groups, preset) => {
  const last = groups[groups.length - 1];
  if (last?.group === preset.group) last.presets.push(preset);
  else groups.push({ group: preset.group, presets: [preset] });
  return groups;
}, []);

const MODE_OPTIONS: {
  value: ConversionMode;
  label: string;
  description: string;
}[] = [
  {
    value: "transcribe",
    label: "Faithful transcription",
    description:
      "Keeps exactly what is on the page. Good when your notes are already complete.",
  },
  {
    value: "material",
    label: "Student notes (fills in explanations)",
    description:
      "Keeps your notes and adds short explanations where a step was skipped.",
  },
];

const PIPELINE_OPTIONS: {
  value: "single" | "split";
  label: string;
  description: string;
}[] = [
  {
    value: "split",
    label: "Split roles",
    description:
      "One model reads the page, another writes the notes, a third checks the result against the original. Best quality.",
  },
  {
    value: "single",
    label: "Single model",
    description:
      "One vision model does everything. Faster and cheaper, less careful.",
  },
];

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-border pt-6 first:border-t-0 first:pt-0">
      <h2 className="margin-rule font-display text-lg">{title}</h2>
      {description && (
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function SettingsPage() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [saved, setSaved] = useState(false);
  const [defaultPreamble, setDefaultPreamble] = useState("");

  useEffect(() => {
    fetchDefaultPreamble()
      .then((preamble) => {
        setDefaultPreamble(preamble);
        // If no custom preamble is set yet, populate with the default
        setSettings((prev) => {
          if (!prev.preamble) {
            return { ...prev, preamble };
          }
          return prev;
        });
      })
      .catch(() => {});
  }, []);

  const update = (patch: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
    setSaved(false);
  };

  const handleSave = () => {
    saveSettings(settings);
    setSaved(true);
  };

  const preset = presetForModel(settings.model);
  const providerValue =
    settings.useCustomModel || !preset ? "custom" : preset.id;

  const chooseProvider = (value: string) => {
    if (value === "custom") {
      // Start from a clean slate: a custom model usually targets a different
      // endpoint than whatever preset was selected before.
      update({ useCustomModel: true, apiBase: "" });
      return;
    }
    const next = PROVIDER_PRESETS.find((p) => p.id === value);
    if (!next) return;
    update({
      useCustomModel: false,
      model: next.model,
      apiBase: next.apiBase,
    });
  };

  return (
    <main className="mx-auto max-w-2xl px-4 pb-20">
      <Button
        variant="ghost"
        size="sm"
        className="mt-6 -ml-2 text-muted-foreground"
        onClick={() => navigate("/")}
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back
      </Button>

      <div className="mt-4">
        <h1 className="font-display text-3xl tracking-[-0.01em]">
          Settings
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Model, provider, and conversion mode. These are saved in this browser
          and used for every conversion.
        </p>
      </div>

      <div className="mt-8 space-y-6 border border-border bg-card px-5 py-6 sm:px-6">
        <Section
          title="Provider"
          description="Hack Club AI is the default. Any OpenAI-compatible endpoint works."
        >
          <div className="space-y-2">
            <Label htmlFor="provider">Provider and model</Label>
            <Select value={providerValue} onValueChange={chooseProvider}>
              <SelectTrigger id="provider" className="w-full">
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                {PRESET_GROUPS.map(({ group, presets }) => (
                  <SelectGroup key={group}>
                    <SelectLabel>{group}</SelectLabel>
                    {presets.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
                <SelectGroup>
                  <SelectLabel>Custom</SelectLabel>
                  <SelectItem value="custom">Custom model string</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            {!settings.useCustomModel && preset && (
              <p className="font-mono text-xs text-muted-foreground">
                {preset.model}
              </p>
            )}
          </div>

          {settings.useCustomModel && (
            <div className="mt-4 space-y-2">
              <Label htmlFor="custom-model">Model string</Label>
              <Input
                id="custom-model"
                className="font-mono text-sm"
                placeholder="openai/your-model-id"
                spellCheck={false}
                autoComplete="off"
                value={settings.customModel}
                onChange={(e) => update({ customModel: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Use the provider-prefixed form your server expects, such as{" "}
                <code className="font-mono">openrouter/google/gemini-3-flash-preview</code>
                .
              </p>
            </div>
          )}

          <div className="mt-4 space-y-2">
            <Label htmlFor="api-base">Base URL</Label>
            <Input
              id="api-base"
              type="url"
              inputMode="url"
              className="font-mono text-sm"
              placeholder={preset?.apiBase ?? "https://example.com/v1"}
              spellCheck={false}
              autoComplete="off"
              value={settings.apiBase}
              onChange={(e) => update({ apiBase: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              The OpenAI-compatible endpoint the server calls. Leave it blank to
              use the server's own default.
            </p>
          </div>
        </Section>

        <Section
          title="API key"
          description="Stored only in this browser and sent with each request."
        >
          <div className="space-y-2">
            <Label htmlFor="api-key">Key</Label>
            <Input
              id="api-key"
              type="password"
              className="font-mono text-sm"
              placeholder="sk-..."
              autoComplete="off"
              value={settings.apiKey}
              onChange={(e) => update({ apiKey: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Leave it blank to use the key your server is configured with. Keys
              for Hack Club AI come from{" "}
              <a
                href="https://ai.hackclub.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-border underline-offset-4 hover:text-ink hover:decoration-ink"
              >
                ai.hackclub.com
              </a>
              .
            </p>
          </div>
        </Section>

        <Section
          title="Conversion mode"
          description="What the model should do with each page."
        >
          <fieldset>
            <legend className="sr-only">Conversion mode</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {MODE_OPTIONS.map((option) => {
                const active = settings.mode === option.value;
                return (
                  <label
                    key={option.value}
                    className={cn(
                      "cursor-pointer border px-3 py-3 transition-colors",
                      active
                        ? "border-ink bg-ink/[0.04]"
                        : "border-border hover:border-ink/40",
                      "has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40",
                    )}
                  >
                    <input
                      type="radio"
                      name="conversion-mode"
                      value={option.value}
                      checked={active}
                      onChange={() => update({ mode: option.value })}
                      className="sr-only"
                    />
                    <span className="block text-sm font-medium">
                      {option.label}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                      {option.description}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </Section>

        <Section
          title="Pipeline"
          description="Which models do the work. Split roles use one model to read the page, another to write it, and a third to check the result against the original."
        >
          <fieldset>
            <legend className="sr-only">Pipeline</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {PIPELINE_OPTIONS.map((option) => {
                const active = settings.pipeline === option.value;
                return (
                  <label
                    key={option.value}
                    className={cn(
                      "cursor-pointer border px-3 py-3 transition-colors",
                      active
                        ? "border-ink bg-ink/[0.04]"
                        : "border-border hover:border-ink/40",
                      "has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40",
                    )}
                  >
                    <input
                      type="radio"
                      name="pipeline"
                      value={option.value}
                      checked={active}
                      onChange={() => update({ pipeline: option.value })}
                      className="sr-only"
                    />
                    <span className="block text-sm font-medium">
                      {option.label}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                      {option.description}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </Section>

        <Section
          title="LaTeX preamble"
          description="Applies to every conversion. Add your own packages, commands, and theorem styles."
        >
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="preamble">Preamble</Label>
              {defaultPreamble && settings.preamble !== defaultPreamble && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() =>
                    update({
                      preamble: defaultPreamble,
                      preambleIsCustom: false,
                    })
                  }
                >
                  <RotateCcw className="mr-1 h-3 w-3" />
                  Reset to default
                </Button>
              )}
            </div>
            <Textarea
              id="preamble"
              className="min-h-[320px] resize-y font-mono text-xs leading-relaxed"
              value={settings.preamble}
              onChange={(e) =>
                update({
                  preamble: e.target.value,
                  preambleIsCustom:
                    e.target.value.trim() !== defaultPreamble.trim(),
                })
              }
              spellCheck={false}
            />
            <p className="text-xs text-muted-foreground">
              The default is only shown for reference; it is not sent to the
              server unless you edit it.
            </p>
          </div>
        </Section>

        <div className="flex flex-wrap items-center gap-4 border-t border-border pt-6">
          <Button onClick={handleSave}>Save settings</Button>
          {saved && (
            <span className="text-sm text-muted-foreground">Saved</span>
          )}
          <a
            href="https://docs.litellm.ai/docs/providers"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-ink hover:decoration-ink"
          >
            Supported providers
            <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        </div>
      </div>
    </main>
  );
}
