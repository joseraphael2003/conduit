import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { AmberBar } from "@/components/AmberBar";
import {
  Shuffle,
  Download,
  Play,
  FilmStrip,
  CaretDown,
  CaretUp,
  Warning,
} from "@phosphor-icons/react";
import { apiBase } from "@/config";

interface Segment {
  segment_index: number;
  script_line: string;
  start_time: number;
  end_time: number;
  duration: number;
  effect: string;
}

interface VideoStatus {
  status: "idle" | "processing" | "completed" | "error";
  current_segment: number;
  total_segments: number;
  message: string;
}

const EFFECTS = [
  { value: "none", label: "No Effect" },
  { value: "pan_left", label: "Pan Left" },
  { value: "pan_right", label: "Pan Right" },
  { value: "pan_up", label: "Pan Up" },
  { value: "pan_down", label: "Pan Down" },
  { value: "zoom_in", label: "Zoom In" },
  { value: "zoom_out", label: "Zoom Out" },
];



const getRandomEffect = (): string => {
  const motionEffects = EFFECTS.filter((e) => e.value !== "none");
  return motionEffects[Math.floor(Math.random() * motionEffects.length)].value;
};

export function Step5Video() {
  const { uuid } = useParams<{ uuid: string }>();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [effects, setEffects] = useState<Record<number, string>>({});
  const [imageStatuses, setImageStatuses] = useState<Record<number, boolean>>({});
  const [burnCaptions, setBurnCaptions] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [videoComplete, setVideoComplete] = useState(false);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [showConsole, setShowConsole] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasAutoAssigned = useRef(false);
  const consoleRef = useRef<HTMLDivElement>(null);
  const lastLogCount = useRef(0);

  const missingImagesCount =
    segments.length - Object.values(imageStatuses).filter(Boolean).length;

  const fetchSegments = useCallback(async (signal?: AbortSignal) => {
    if (!uuid) return;
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/segments`, { signal });
      if (!response.ok) {
        if (response.status === 404) {
          setSegments([]);
          setLoading(false);
          return;
        }
        throw new Error(`Failed to fetch segments: ${response.status}`);
      }
      const data = (await response.json()) as { segments: Segment[] };
      const fetchedSegments = data.segments || [];
      setSegments(fetchedSegments);

      const initialEffects: Record<number, string> = {};
      fetchedSegments.forEach((seg) => {
        initialEffects[seg.segment_index] = seg.effect || "none";
      });
      setEffects(initialEffects);

      const allNone = fetchedSegments.every(
        (seg) => (seg.effect || "none") === "none"
      );
      if (allNone && fetchedSegments.length > 0 && !hasAutoAssigned.current) {
        hasAutoAssigned.current = true;
        const newEffects: Record<number, string> = {};
        for (const seg of fetchedSegments) {
          const randomEffect = getRandomEffect();
          newEffects[seg.segment_index] = randomEffect;
          try {
            await fetch(
              `${apiBase}/projects/${uuid}/segments/${seg.segment_index}/effect`,
              {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ effect: randomEffect }),
                signal,
              }
            );
          } catch {
            // Silent fail for individual effect updates during auto-assign
          }
        }
        setEffects(newEffects);
        setSegments((prev) =>
          prev.map((seg) => ({
            ...seg,
            effect: newEffects[seg.segment_index],
          }))
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [uuid]);

  const checkImageStatus = useCallback(
    async (segmentIndex: number) => {
      if (!uuid) return;
      try {
        const response = await fetch(
          `${apiBase}/projects/${uuid}/images/${segmentIndex}`
        );
        setImageStatuses((prev) => ({
          ...prev,
          [segmentIndex]: response.ok,
        }));
      } catch {
        setImageStatuses((prev) => ({
          ...prev,
          [segmentIndex]: false,
        }));
      }
    },
    [uuid]
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchSegments(controller.signal);
    return () => controller.abort();
  }, [fetchSegments]);

  useEffect(() => {
    if (segments.length > 0) {
      segments.forEach((seg) => {
        checkImageStatus(seg.segment_index);
      });
    }
  }, [segments, checkImageStatus]);

  useEffect(() => {
    if (!generating) return;

    const interval = setInterval(async () => {
      if (!uuid) return;
      try {
        const response = await fetch(`${apiBase}/projects/${uuid}/video/status`);
        if (!response.ok) return;
        const status = (await response.json()) as VideoStatus;
        setVideoStatus(status);

        if (status.message) {
          setConsoleOutput((prev) => {
            if (prev.length === 0 || prev[prev.length - 1] !== status.message) {
              return [...prev, status.message];
            }
            return prev;
          });
        }

        if (status.status === "completed") {
          setGenerating(false);
          setVideoComplete(true);
          setConsoleOutput((prev) => [...prev, "Video generation complete."]);
        } else if (status.status === "error") {
          setGenerating(false);
          setError(status.message);
          setConsoleOutput((prev) => [...prev, `Error: ${status.message}`]);
        }
      } catch {
        // Silent fail during polling
      }

      // Fetch ffmpeg stderr logs
      try {
        const logsResponse = await fetch(`${apiBase}/projects/${uuid}/video/logs`);
        if (logsResponse.ok) {
          const logsData = (await logsResponse.json()) as { lines: string[] };
          const lines = logsData.lines;
          const newLines = lines.slice(lastLogCount.current);
          if (newLines.length > 0) {
            setConsoleOutput((prev) => [...prev, ...newLines]);
            lastLogCount.current = lines.length;
          }
        }
      } catch {
        // Silent fail during log polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [generating, uuid]);

  useEffect(() => {
    if (consoleRef.current && showConsole) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [consoleOutput, showConsole]);

  const handleEffectChange = async (segmentIndex: number, effect: string) => {
    if (!uuid) return;
    setEffects((prev) => ({ ...prev, [segmentIndex]: effect }));
    setSegments((prev) =>
      prev.map((seg) =>
        seg.segment_index === segmentIndex ? { ...seg, effect } : seg
      )
    );

    try {
      const response = await fetch(
        `${apiBase}/projects/${uuid}/segments/${segmentIndex}/effect`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ effect }),
        }
      );
      if (!response.ok) {
        throw new Error(`Failed to update effect: ${response.status}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update effect");
    }
  };

  const handleRandomize = async () => {
    if (!uuid || segments.length === 0) return;
    const newEffects: Record<number, string> = {};
    for (const seg of segments) {
      const randomEffect = getRandomEffect();
      newEffects[seg.segment_index] = randomEffect;
    }
    setEffects(newEffects);
    setSegments((prev) =>
      prev.map((seg) => ({
        ...seg,
        effect: newEffects[seg.segment_index],
      }))
    );

    for (const seg of segments) {
      try {
        await fetch(
          `${apiBase}/projects/${uuid}/segments/${seg.segment_index}/effect`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ effect: newEffects[seg.segment_index] }),
          }
        );
      } catch {
        // Silent fail for individual updates
      }
    }
  };

  const handleDownloadSrt = () => {
    if (!uuid) return;
    window.open(`${apiBase}/projects/${uuid}/video/srt`, "_blank");
  };

  const handleGenerateVideo = async () => {
    if (!uuid) return;
    if (missingImagesCount > 0) return;

    setGenerating(true);
    setVideoComplete(false);
    setError(null);
    setConsoleOutput([]);
    setVideoStatus(null);
    lastLogCount.current = 0;

    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/video/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ burn_captions: burnCaptions }),
      });

      if (!response.ok) {
        const errorData = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(
          errorData.detail || `Generation failed: ${response.status}`
        );
      }

      const data = (await response.json()) as {
        output_path: string;
        duration: number;
      };
      setConsoleOutput((prev) => [
        ...prev,
        `Video generation completed: ${data.output_path}`,
      ]);
      setGenerating(false);
      setVideoComplete(true);
    } catch (err) {
      setGenerating(false);
      const message = err instanceof Error ? err.message : "Generation failed";
      setError(message);
      setConsoleOutput((prev) => [...prev, `Error: ${message}`]);
    }
  };

  const handleDownloadVideo = () => {
    if (!uuid) return;
    window.open(`${apiBase}/projects/${uuid}/video/download`, "_blank");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[400px]">
        <AmberBar />
        <span className="font-body text-[#8A8A9A] ml-3">
          Loading segments...
        </span>
      </div>
    );
  }

  if (error && segments.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px]">
        <span className="font-body text-[#EF4444] text-lg">
          Error: {error}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-headline text-2xl text-[#E8E8F0] mb-1">
            Video Generation
          </h2>
          <p className="font-body text-sm text-[#8A8A9A]">
            Assign motion effects to each segment and generate the final video.
          </p>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-3 bg-[#EF4444]/10 border border-[#EF4444]/20 p-3" role="alert" aria-live="assertive">
          <Warning
            size={20}
            weight="regular"
            className="text-[#EF4444] shrink-0"
          />
          <span className="font-body text-sm text-[#EF4444] flex-1">
            {error}
          </span>
        </div>
      )}

      {/* Actions Row */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4 flex-wrap">
          <button
            onClick={handleRandomize}
            disabled={generating || segments.length === 0}
            className={cn(
              "flex items-center gap-2 px-4 py-2 font-body text-sm font-semibold tracking-wide uppercase",
              "bg-[#1A1A24] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#2A2A35]",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
            data-testid="randomize-button"
          >
            <Shuffle size={16} weight="regular" />
            Randomize
          </button>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={burnCaptions}
              onChange={(e) => setBurnCaptions(e.target.checked)}
              className="w-4 h-4 accent-[#F0A040] bg-[#0A0A0F] border border-[#2A2A35]"
              data-testid="burn-captions-checkbox"
            />
            <span className="font-body text-sm text-[#E8E8F0]">
              Burn captions into final video
            </span>
          </label>
        </div>

        <button
          onClick={handleDownloadSrt}
          className={cn(
            "flex items-center gap-2 px-4 py-2 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-[#1A1A24] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#2A2A35]"
          )}
          data-testid="download-srt-button"
        >
          <Download size={16} weight="regular" />
          Download SRT
        </button>
      </div>

      {/* Effect Selection Grid */}
      <div
        className="flex-1 overflow-auto"
        data-testid="effect-selection-grid"
      >
        {segments.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[200px] gap-4">
            <FilmStrip
              size={48}
              weight="regular"
              className="text-[#5A5A6A]"
            />
            <p className="font-body text-sm text-[#8A8A9A] text-center">
              No segments found. Please complete the previous steps first.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {segments.map((segment) => {
              const hasImage = imageStatuses[segment.segment_index] ?? false;
              const currentEffect =
                effects[segment.segment_index] ?? segment.effect ?? "none";

              return (
                <div
                  key={segment.segment_index}
                  className={cn(
                    "bg-[#1A1A24] border border-[#2A2A35] p-3 flex flex-col gap-3",
                    !hasImage && "opacity-60"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">
                      Segment {segment.segment_index}
                    </span>
                    {!hasImage && (
                      <span className="font-mono text-xs text-[#EF4444]">
                        No image
                      </span>
                    )}
                  </div>

                  <div className="flex flex-col gap-1">
                    <span className="font-body text-xs text-[#8A8A9A] line-clamp-2">
                      {segment.script_line}
                    </span>
                    <span className="font-mono text-xs text-[#5A5A6A]">
                      {segment.duration.toFixed(1)}s
                    </span>
                  </div>

                  <select
                    value={currentEffect}
                    onChange={(e) =>
                      handleEffectChange(segment.segment_index, e.target.value)
                    }
                    disabled={generating}
                    className={cn(
                      "w-full bg-[#0A0A0F] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2",
                      "focus:border-[#F0A040] focus:outline-none",
                      "disabled:opacity-50 disabled:cursor-not-allowed"
                    )}
                  >
                    {EFFECTS.map((effect) => (
                      <option key={effect.value} value={effect.value}>
                        {effect.label}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Generate / Download Section */}
      <div className="flex flex-col gap-3">
        {missingImagesCount > 0 && (
          <div className="flex items-center gap-2 text-[#EF4444]">
            <Warning size={16} weight="regular" />
            <span className="font-body text-sm">
              Upload images for all segments before generating.{" "}
              {missingImagesCount} segments missing.
            </span>
          </div>
        )}

        <div className="flex items-center justify-between">
          {!videoComplete ? (
            <button
              onClick={handleGenerateVideo}
              disabled={
                generating || missingImagesCount > 0 || segments.length === 0
              }
              className={cn(
                "flex items-center gap-2 px-12 py-4 font-body text-sm font-semibold tracking-wide uppercase",
                "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
              data-testid="generate-video-button"
            >
              {generating ? (
                <AmberBar />
              ) : (
                <Play size={16} weight="regular" />
              )}
              {generating ? "Generating..." : "Generate Video"}
            </button>
          ) : (
            <button
              onClick={handleDownloadVideo}
              className={cn(
                "flex items-center gap-2 px-12 py-4 font-body text-sm font-semibold tracking-wide uppercase",
                "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]"
              )}
              data-testid="download-video-button"
            >
              <Download size={16} weight="regular" />
              Download Video
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {generating && (
        <div
          className="flex flex-col gap-2"
          data-testid="progress-bar"
          role="progressbar"
          aria-valuenow={videoStatus?.current_segment ?? 0}
          aria-valuemax={videoStatus?.total_segments ?? 0}
          aria-label="Video generation progress"
        >
          <div className="w-full h-2 bg-[#1A1A24] border border-[#2A2A35] overflow-hidden">
            <div
              className="h-full bg-[#F0A040] transition-all duration-500 progress-bar-fill"
              style={{
                width: `${
                  videoStatus && videoStatus.total_segments > 0
                    ? (videoStatus.current_segment / videoStatus.total_segments) *
                      100
                    : 0
                }%`,
              }}
            />
          </div>
          <span className="font-mono text-sm text-[#8A8A9A]">
            {videoStatus
              ? `Processing segment ${videoStatus.current_segment} of ${videoStatus.total_segments}...`
              : "Starting generation..."}
          </span>
        </div>
      )}

      {/* Console Output */}
      {(generating || consoleOutput.length > 0) && (
        <div className="flex flex-col gap-2">
          <button
            onClick={() => setShowConsole((prev) => !prev)}
            aria-expanded={showConsole}
            aria-controls="console-output-panel"
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 font-body text-xs font-semibold tracking-wide uppercase",
              "bg-[#1A1A24] text-[#8A8A9A] border border-[#2A2A35] hover:bg-[#2A2A35] self-start"
            )}
            data-testid="console-toggle"
          >
            {showConsole ? (
              <CaretUp size={14} />
            ) : (
              <CaretDown size={14} />
            )}
            Console Output
          </button>

          {showConsole && (
            <div
              id="console-output-panel"
              ref={consoleRef}
              className="bg-[#1A1A24] border border-[#2A2A35] p-3 max-h-[200px] overflow-y-auto"
              data-testid="console-output"
            >
              {consoleOutput.length === 0 ? (
                <span className="font-mono text-xs text-[#5A5A6A]">
                  Waiting for output...
                </span>
              ) : (
                consoleOutput.map((line, index) => (
                  <div
                    key={index}
                    className="font-mono text-xs text-[#8A8A9A] leading-relaxed"
                  >
                    {line}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
