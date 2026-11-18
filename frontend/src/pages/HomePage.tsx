import {
  useState,
  useCallback,
  useEffect,
  useRef,
  type DragEvent,
} from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  Upload,
  X,
  FileText,
  Loader2,
  Clock,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { createJob, listJobs } from "@/lib/api";
import {
  loadSettings,
  getEffectiveModel,
  getEffectiveApiBase,
} from "@/lib/settings";
import { cn } from "@/lib/utils";
import type { JobResponse, JobStatus } from "@/lib/types";

const ACCEPTED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];
const ACCEPTED = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(",");

function StatusBadge({ status }: { status: JobStatus }) {
  switch (status) {
    case "completed":
      return (
        <Badge variant="outline" className="border-ink/25 bg-ink/5 text-ink">
          <CheckCircle2 className="mr-1 h-3 w-3" />
          Completed
        </Badge>
      );
    case "processing":
    case "pending":
      return (
        <Badge
          variant="outline"
          className="border-border bg-muted text-muted-foreground"
        >
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Processing
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="outline"
          className="border-margin/30 bg-margin/5 text-margin"
        >
          <AlertCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function HomePage() {
  const navigate = useNavigate();
  const [settings] = useState(loadSettings);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);

  const uploadRef = useRef<HTMLElement>(null);
  const zoneRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoadingJobs(false));
  }, []);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const arr = Array.from(newFiles).filter((f) => {
      const ext = f.name.toLowerCase().split(".").pop();
      return ACCEPTED_EXTENSIONS.includes(ext ?? "");
    });
    setFiles((prev) => [...prev, ...arr]);
  }, []);

  const openPicker = () => document.getElementById("file-input")?.click();

  const scrollToUpload = () => {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    zoneRef.current?.focus({ preventScroll: true });
  };

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    if (files.length === 0) return;
    setError("");
    setSubmitting(true);

    const model = getEffectiveModel(settings);

    try {
      const res = await createJob(files, {
        model: model || undefined,
        api_key: settings.apiKey || undefined,
        api_base: getEffectiveApiBase(settings),
        mode: settings.mode,
        preamble: settings.preamble || undefined,
      });
      navigate(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-4 pb-20">
      <section className="hero-enter pt-12 pb-12 sm:pt-16">
        <h1 className="font-display text-4xl leading-[1.08] tracking-[-0.01em] text-graphite sm:text-5xl">
          Your board notes, typeset.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Add a photo or a PDF of handwritten pages and get back LaTeX and a
          compiled PDF, ready to hand in.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-4">
          <Button size="lg" onClick={scrollToUpload}>
            Add a page
          </Button>
          <p className="font-mono text-xs text-muted-foreground">
            PDF, PNG, or JPG
          </p>
        </div>

        <div className="mt-10 grid border border-border bg-card md:grid-cols-[1fr_2px_1fr]">
          <figure className="flex flex-col justify-center px-4 py-6 md:px-6">
            <img
              src="/handwriting-hero.png"
              width={640}
              height={104}
              alt="A handwritten line of Gauss's law on ruled notebook paper"
              className="w-full"
            />
            <figcaption className="mt-4 font-mono text-xs text-muted-foreground">
              Handwritten, page 1
            </figcaption>
          </figure>
          <div
            aria-hidden
            className="h-[2px] w-full bg-margin md:h-auto md:w-[2px]"
          />
          <figure className="flex flex-col justify-center px-4 py-6 md:px-6">
            <p className="font-display text-xl leading-relaxed text-ink sm:text-2xl">
              Φ<sub className="text-[0.65em]">E</sub> = ∮
              <sub className="-ml-[0.14em] text-[0.65em]">S</sub> E · dA = q
              <sub className="text-[0.65em]">enc</sub> / ε
              <sub className="text-[0.65em]">0</sub>
            </p>
            <figcaption className="mt-4 font-mono text-xs text-muted-foreground">
              Typeset in LaTeX
            </figcaption>
          </figure>
        </div>
      </section>

      <section
        id="upload"
        ref={uploadRef}
        className="scroll-mt-20 border-t border-border pt-10"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="margin-rule font-display text-2xl">Add your pages</h2>
          <Link
            to="/settings"
            className="text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-ink hover:decoration-ink"
          >
            Conversion settings
          </Link>
        </div>
        <p className="mt-3 max-w-xl text-sm text-muted-foreground">
          Pages convert in the order you add them.
        </p>

        <div
          ref={zoneRef}
          role="button"
          tabIndex={0}
          aria-label="Add pages to convert"
          onClick={openPicker}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openPicker();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
              setDragOver(false);
            }
          }}
          onDrop={onDrop}
          className={cn(
            "ruled-paper relative mt-6 cursor-pointer border border-border px-6 py-12 pl-16 text-center outline-none transition-colors sm:pl-20",
            "hover:border-ink/40 hover:bg-ink/[0.02]",
            "focus-visible:border-ink focus-visible:ring-[3px] focus-visible:ring-ring/40",
            dragOver && "border-ink bg-ink/[0.04]",
          )}
        >
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 left-10 w-[2px] bg-margin sm:left-14"
          />
          <Upload className="mx-auto h-6 w-6 text-ink" aria-hidden />
          <p className="mt-3 text-base font-medium">
            Drop pages here, or click to browse.
          </p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            PDF, PNG, or JPG. Several files at once is fine.
          </p>
          <input
            id="file-input"
            type="file"
            accept={ACCEPTED}
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </div>

        {files.length > 0 && (
          <ul className="mt-4 divide-y divide-border border border-border bg-card">
            {files.map((f, i) => (
              <li
                key={`${f.name}-${i}`}
                className="flex items-center gap-3 px-4 py-2 text-sm"
              >
                <FileText
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate">{f.name}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {formatSize(f.size)}
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${f.name}`}
                  className="rounded-sm p-1 text-muted-foreground outline-none transition-colors hover:text-margin focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button
            size="lg"
            disabled={files.length === 0 || submitting}
            onClick={handleSubmit}
            className="sm:min-w-52"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting conversion…
              </>
            ) : (
              "Convert to LaTeX"
            )}
          </Button>
          <p className="text-sm text-muted-foreground">
            {settings.mode === "transcribe"
              ? "Faithful transcription"
              : "Student notes"}{" "}
            mode.{" "}
            <Link
              to="/settings"
              className="underline decoration-border underline-offset-4 hover:text-ink hover:decoration-ink"
            >
              Change
            </Link>
          </p>
        </div>
      </section>

      <section className="mt-16">
        <h2 className="margin-rule font-display text-2xl">
          Recent conversions
        </h2>
        {loadingJobs ? (
          <p className="mt-5 font-mono text-xs text-muted-foreground">
            Loading…
          </p>
        ) : jobs.length === 0 ? (
          <p className="mt-5 text-sm text-muted-foreground">
            Nothing here yet. Finished conversions will show up in this list.
          </p>
        ) : (
          <ul className="mt-5 divide-y divide-border border border-border bg-card">
            {jobs.map((job) => (
              <li key={job.job_id}>
                <Link
                  to={`/jobs/${job.job_id}`}
                  className="flex items-center gap-4 px-4 py-3 outline-none transition-colors hover:bg-ink/[0.03] focus-visible:bg-ink/[0.03] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {job.input_filenames.join(", ")}
                    </span>
                    <span className="mt-1 flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" aria-hidden />
                      {formatDate(job.created_at)}
                      {job.total_pages > 0 &&
                        `, ${job.total_pages} page${job.total_pages !== 1 ? "s" : ""}`}
                    </span>
                  </span>
                  <StatusBadge status={job.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
