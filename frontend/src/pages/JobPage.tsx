import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Loader2,
  AlertCircle,
  Download,
  FileText,
  File,
  Archive,
  ArrowLeft,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Filter,
  FilterX,
} from "lucide-react";
import { useCopyToClipboard } from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { modeLabel } from "@/lib/settings";
import {
  subscribeToJob,
  getJob,
  fetchTexSource,
  downloadUrl,
  getJobPages,
  getPageLatex,
  pageImageUrl,
} from "@/lib/api";
import type { ProgressEvent, JobResponse } from "@/lib/types";

function humanStatus(event: ProgressEvent): string {
  switch (event.event_type) {
    case "job_started":
      return `Starting conversion of ${event.total_pages} page${event.total_pages !== 1 ? "s" : ""}...`;
    case "page_generating":
      return `Transcribing page ${event.page} of ${event.total_pages}...`;
    case "page_compiling":
      return `Compiling page ${event.page} of ${event.total_pages}...`;
    case "page_compiled_ok":
      return `Page ${event.page} compiled successfully`;
    case "page_fix_attempt":
      return `Fixing compilation errors on page ${event.page} (attempt ${event.retry} of ${event.max_retries})...`;
    case "page_done":
      return `Page ${event.page} of ${event.total_pages} done`;
    case "finalizing":
      return "Assembling final document...";
    case "job_completed":
      return "Conversion complete";
    case "job_failed":
      return event.message || "Conversion failed";
    default:
      return event.message || "Processing...";
  }
}

function ProcessingView({
  latestEvent,
}: {
  latestEvent: ProgressEvent | null;
}) {
  const totalPages = latestEvent?.total_pages ?? 0;
  const currentPage = latestEvent?.page ?? 0;
  // Count completed pages (page_done events advance this)
  const progressPercent =
    totalPages > 0 ? Math.round((currentPage / totalPages) * 100) : 0;
  const statusText = latestEvent ? humanStatus(latestEvent) : "Connecting...";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-display text-xl">
          <Loader2 className="h-5 w-5 animate-spin text-ink" />
          Converting
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between gap-4 text-sm">
            <span className="text-muted-foreground">{statusText}</span>
            {totalPages > 0 && (
              <span className="font-mono text-xs">{progressPercent}%</span>
            )}
          </div>
          <Progress value={progressPercent} />
        </div>
      </CardContent>
    </Card>
  );
}

function SplitLabel({ children }: { children: ReactNode }) {
  return (
    <h3 className="font-mono text-xs text-muted-foreground">{children}</h3>
  );
}

function ReviewTab({ jobId }: { jobId: string }) {
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageLatex, setPageLatex] = useState<string | null>(null);
  const { copied, copy } = useCopyToClipboard();
  const latexCache = useRef(new Map<number, string>());

  // Fetch page count on mount
  useEffect(() => {
    getJobPages(jobId)
      .then((data) => {
        setTotalPages(data.total_pages);
      })
      .catch(() => setTotalPages(0));
  }, [jobId]);

  // Fetch LaTeX for current page (with cache)
  useEffect(() => {
    if (totalPages === 0) return;
    const cached = latexCache.current.get(currentPage);
    if (cached !== undefined) {
      setPageLatex(cached);
      return;
    }
    let cancelled = false;
    getPageLatex(jobId, currentPage)
      .then((data) => {
        if (!cancelled) {
          latexCache.current.set(currentPage, data.latex);
          setPageLatex(data.latex);
        }
      })
      .catch(() => {
        if (!cancelled) setPageLatex("Failed to load LaTeX for this page.");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, currentPage, totalPages]);

  if (totalPages === 0) {
    return (
      <p className="border border-border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
        No page data available for review.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Page navigation */}
      <div className="flex items-center justify-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          disabled={currentPage <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <span className="min-w-[7.5rem] text-center font-mono text-xs text-muted-foreground">
          Page {currentPage} of {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          disabled={currentPage >= totalPages}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* The page and its typeset twin, split by the notebook margin rule */}
      <div className="border border-border bg-card">
        <div className="grid md:grid-cols-[1fr_2px_1fr]">
          <div className="min-w-0">
            <div className="border-b border-border px-4 py-2">
              <SplitLabel>Original, page {currentPage}</SplitLabel>
            </div>
            <div className="max-h-[70vh] overflow-auto bg-muted/30 p-2">
              <img
                src={pageImageUrl(jobId, currentPage)}
                alt={`Original page ${currentPage}`}
                className="h-auto w-full"
              />
            </div>
          </div>

          <div
            aria-hidden
            className="h-[2px] w-full bg-margin md:h-auto md:w-[2px]"
          />

          <div className="min-w-0">
            <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
              <SplitLabel>LaTeX, page {currentPage}</SplitLabel>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => pageLatex && copy(pageLatex)}
                disabled={!pageLatex}
              >
                {copied ? (
                  <>
                    <Check className="mr-1 h-3 w-3" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="mr-1 h-3 w-3" />
                    Copy
                  </>
                )}
              </Button>
            </div>
            <div className="p-2">
              {!pageLatex ? (
                <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </div>
              ) : (
                <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap bg-muted/40 p-4 font-mono text-xs leading-relaxed">
                  {pageLatex}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Split LaTeX source into segments by page markers.
 * Content before the first marker (preamble) gets page_number = 0.
 */
function splitByPageMarkers(
  tex: string,
): { page_number: number; content: string }[] {
  const segments: { page_number: number; content: string }[] = [];
  const lines = tex.split("\n");
  let currentPage = 0;
  let currentLines: string[] = [];

  for (const line of lines) {
    const match = line.match(/^% ====== Page (\d+) ======$/);
    if (match) {
      if (currentLines.length > 0) {
        segments.push({
          page_number: currentPage,
          content: currentLines.join("\n"),
        });
      }
      currentPage = parseInt(match[1], 10);
      currentLines = [line];
    } else {
      currentLines.push(line);
    }
  }
  if (currentLines.length > 0) {
    segments.push({
      page_number: currentPage,
      content: currentLines.join("\n"),
    });
  }

  return segments;
}

function LatexSourceView({
  texSource,
  texLoading,
}: {
  texSource: string | null;
  texLoading: boolean;
}) {
  const { copied, copy } = useCopyToClipboard();
  const [filterPage, setFilterPage] = useState<number | null>(null);
  const preRef = useRef<HTMLPreElement>(null);

  const segments = useMemo(
    () => (texSource ? splitByPageMarkers(texSource) : []),
    [texSource],
  );

  const pageNumbers = useMemo(
    () => segments.filter((s) => s.page_number > 0).map((s) => s.page_number),
    [segments],
  );

  const pendingScrollRef = useRef<number | null>(null);

  const scrollToPage = (pageNum: number) => {
    if (!preRef.current) return;
    pendingScrollRef.current = pageNum;
    setFilterPage(null);
  };

  // Scroll to page marker after filter clears and DOM updates
  useEffect(() => {
    const pageNum = pendingScrollRef.current;
    if (pageNum === null || filterPage !== null) return;
    pendingScrollRef.current = null;
    const marker = preRef.current?.querySelector(`[data-page="${pageNum}"]`);
    if (marker) {
      marker.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [filterPage]);

  const toggleFilter = (pageNum: number) => {
    setFilterPage((prev) => (prev === pageNum ? null : pageNum));
  };

  const displayedSegments = useMemo(() => {
    if (filterPage === null) return segments;
    return segments.filter(
      (s) => s.page_number === 0 || s.page_number === filterPage,
    );
  }, [segments, filterPage]);

  if (texLoading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {pageNumbers.length > 0 && (
            <>
              <span className="mr-1 font-mono text-xs text-muted-foreground">
                Pages
              </span>
              {pageNumbers.map((p) => (
                <Button
                  key={p}
                  variant={filterPage === p ? "default" : "outline"}
                  size="sm"
                  className="h-7 w-7 p-0 font-mono text-xs"
                  onClick={() => scrollToPage(p)}
                  onDoubleClick={() => toggleFilter(p)}
                  title={`Click to scroll to page ${p}, double-click to filter`}
                >
                  {p}
                </Button>
              ))}
              {filterPage !== null && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-7 px-2 text-xs"
                  onClick={() => setFilterPage(null)}
                >
                  <FilterX className="h-3 w-3 mr-1" />
                  Show all
                </Button>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {filterPage !== null && (
            <Badge variant="secondary" className="text-xs">
              <Filter className="mr-1 h-3 w-3" />
              Page {filterPage} only
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => texSource && copy(texSource)}
            disabled={!texSource}
          >
            {copied ? (
              <>
                <Check className="mr-2 h-3 w-3" />
                Copied
              </>
            ) : (
              <>
                <Copy className="mr-2 h-3 w-3" />
                Copy
              </>
            )}
          </Button>
        </div>
      </div>

      <pre
        ref={preRef}
        className="max-h-[60vh] overflow-auto whitespace-pre-wrap bg-muted/40 p-4 font-mono text-xs leading-relaxed"
      >
        {displayedSegments.map((segment, idx) => {
          const newlinePos = segment.content.indexOf("\n");
          const markerLine =
            newlinePos >= 0
              ? segment.content.slice(0, newlinePos)
              : segment.content;
          const bodyContent =
            newlinePos >= 0 ? segment.content.slice(newlinePos + 1) : "";

          return (
            <span key={`${segment.page_number}-${idx}`}>
              {segment.page_number > 0 ? (
                <>
                  <span
                    data-page={segment.page_number}
                    className="my-2 -ml-2 block border-l-2 border-ink bg-ink/5 py-0.5 pl-2 font-medium text-ink"
                  >
                    {markerLine}
                  </span>
                  {bodyContent}
                </>
              ) : (
                segment.content
              )}
              {idx < displayedSegments.length - 1 ? "\n" : ""}
            </span>
          );
        })}
      </pre>
    </div>
  );
}

function CdnLinks({ urls }: { urls?: Record<string, string> | null }) {
  const entries = useMemo(
    () =>
      Object.entries(urls ?? {}).sort(
        ([a], [b]) => Number(a) - Number(b),
      ),
    [urls],
  );

  if (entries.length === 0) return null;

  return (
    <div>
      <p className="font-mono text-xs text-muted-foreground">
        Originals on Hack Club CDN
      </p>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        {entries.map(([page, url]) => (
          <a
            key={page}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-ink underline decoration-rule underline-offset-4 hover:decoration-ink"
          >
            Page {page}
          </a>
        ))}
      </div>
    </div>
  );
}

function ResultView({ job }: { job: JobResponse }) {
  const [texSource, setTexSource] = useState<string | null>(null);
  const [texLoading, setTexLoading] = useState(false);

  const loadTex = useCallback(() => {
    if (texSource !== null || texLoading || !job.has_tex) return;
    setTexLoading(true);
    fetchTexSource(job.job_id)
      .then(setTexSource)
      .catch(() => setTexSource("Failed to load source."))
      .finally(() => setTexLoading(false));
  }, [job.job_id, job.has_tex, texSource, texLoading]);

  const meta = [
    job.input_filenames.join(", "),
    job.total_pages > 0
      ? `${job.total_pages} page${job.total_pages !== 1 ? "s" : ""}`
      : null,
    job.mode ? modeLabel(job.mode).toLowerCase() : null,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="margin-rule font-display text-3xl tracking-[-0.01em]">
            Review
          </h1>
          <p className="mt-2 max-w-xl font-mono text-xs text-muted-foreground">
            {meta.join(", ")}
          </p>
        </div>
        <CdnLinks urls={job.cdn_urls} />
      </header>

      {job.has_pdf && (
        <div className="border border-border bg-card">
          <iframe
            src={downloadUrl(job.job_id, "output.pdf")}
            className="w-full"
            style={{ height: "70vh" }}
            title="PDF preview"
          />
        </div>
      )}

      {!job.has_pdf && job.has_tex && (
        <p className="flex items-start gap-2 border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          The PDF did not compile, but the .tex source was saved. Download it
          and compile it locally.
        </p>
      )}

      {job.editorial_notes && (
        <section className="border border-border bg-card">
          <div className="border-b border-border px-5 py-3">
            <h2 className="margin-rule font-display text-lg">
              Editorial notes
            </h2>
          </div>
          <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap px-5 py-4 font-sans text-sm leading-relaxed text-graphite">
            {job.editorial_notes}
          </pre>
        </section>
      )}

      {/* Tabs: Review / Downloads / LaTeX Source */}
      <Tabs
        defaultValue="review"
        onValueChange={(v) => {
          if (v === "source") loadTex();
        }}
      >
        <TabsList variant="line">
          <TabsTrigger value="review" className="after:bg-ink">
            Review
          </TabsTrigger>
          <TabsTrigger value="downloads" className="after:bg-ink">
            Downloads
          </TabsTrigger>
          {job.has_tex && (
            <TabsTrigger value="source" className="after:bg-ink">
              LaTeX source
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="review">
          <ReviewTab jobId={job.job_id} />
        </TabsContent>

        <TabsContent value="downloads">
          <div className="grid gap-3 border border-border bg-card p-4">
            {job.has_pdf && (
              <a href={downloadUrl(job.job_id, "output.pdf", true)}>
                <Button
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <File className="h-4 w-4" />
                  Download PDF
                  <Download className="ml-auto h-4 w-4" />
                </Button>
              </a>
            )}
            {job.has_tex && (
              <a href={downloadUrl(job.job_id, "output.tex", true)}>
                <Button
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <FileText className="h-4 w-4" />
                  Download .tex source
                  <Download className="ml-auto h-4 w-4" />
                </Button>
              </a>
            )}
            <a href={downloadUrl(job.job_id, "all.zip", true)}>
              <Button variant="outline" className="w-full justify-start gap-2">
                <Archive className="h-4 w-4" />
                Download all (.zip)
                <Download className="ml-auto h-4 w-4" />
              </Button>
            </a>
          </div>
        </TabsContent>

        {job.has_tex && (
          <TabsContent value="source">
            <div className="border border-border bg-card p-4">
              <LatexSourceView texSource={texSource} texLoading={texLoading} />
            </div>
          </TabsContent>
        )}
      </Tabs>

      <Button asChild variant="outline" className="w-full">
        <Link to="/">Add another page</Link>
      </Button>
    </div>
  );
}

function FailedView({ errorMessage }: { errorMessage: string }) {
  return (
    <div className="border border-margin/30 bg-card">
      <div className="border-b border-border px-5 py-4">
        <h1 className="flex items-center gap-2 font-display text-xl text-margin">
          <AlertCircle className="h-5 w-5" />
          Conversion failed
        </h1>
      </div>
      <div className="space-y-4 px-5 py-4">
        <p className="text-sm text-muted-foreground">{errorMessage}</p>
        <Button asChild>
          <Link to="/">Try again</Link>
        </Button>
      </div>
    </div>
  );
}

export function JobPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [latestEvent, setLatestEvent] = useState<ProgressEvent | null>(null);
  const [status, setStatus] = useState<
    "loading" | "processing" | "completed" | "failed"
  >("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    // Fetch initial job state
    getJob(id)
      .then((j) => {
        if (cancelled) return;
        setJob(j);
        if (j.status === "completed") {
          setStatus("completed");
          return;
        }
        if (j.status === "failed") {
          setStatus("failed");
          setErrorMessage(j.error_message ?? "Unknown error");
          return;
        }

        // Job is pending/processing — connect SSE (replays all past events)
        setStatus("processing");
        if (cancelled) return;
        const unsub = subscribeToJob(
          id,
          (event: ProgressEvent) => {
            if (cancelled) return;
            setLatestEvent(event);
            if (event.event_type === "job_completed") {
              // Refetch job to get has_pdf/has_tex
              getJob(id).then((updated) => {
                if (cancelled) return;
                setJob(updated);
                setStatus("completed");
              });
            } else if (event.event_type === "job_failed") {
              setStatus("failed");
              setErrorMessage(event.message);
            }
          },
          undefined,
          () => {
            if (cancelled) return;
            // SSE error — job might have finished while we were away
            getJob(id).then((j) => {
              if (cancelled) return;
              setJob(j);
              if (j.status === "completed") setStatus("completed");
              else if (j.status === "failed") {
                setStatus("failed");
                setErrorMessage(j.error_message ?? "Unknown error");
              }
            });
          },
        );
        unsubRef.current = unsub;
      })
      .catch(() => {
        if (!cancelled) navigate("/");
      });

    return () => {
      cancelled = true;
      unsubRef.current?.();
    };
  }, [id, navigate]);

  if (status === "loading") {
    return (
      <main className="mx-auto max-w-4xl px-4 py-12 text-center font-mono text-xs text-muted-foreground">
        Loading…
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 pb-20 pt-6">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-2 text-muted-foreground"
        asChild
      >
        <Link to="/">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Link>
      </Button>

      <div className="mt-4">
        {status === "processing" && (
          <ProcessingView latestEvent={latestEvent} />
        )}
        {status === "completed" && job && <ResultView job={job} />}
        {status === "failed" && <FailedView errorMessage={errorMessage} />}
      </div>
    </main>
  );
}
