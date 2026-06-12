import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { CopyButton } from "@/components/CopyButton";
import { Upload, Info, Image as ImageIcon, X } from "@phosphor-icons/react";
import { apiBase } from "@/config";

interface Segment {
  segment_index: number;
  script_line: string;
  segment_prompt: string;
  characters_present: string[];
  start_time: number;
  end_time: number;
}

interface Step4ImagesProps {
  onStateChange?: () => void;
}

export function Step4Images({ onStateChange }: Step4ImagesProps) {
  const { uuid } = useParams<{ uuid: string }>();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [imageStatuses, setImageStatuses] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  const [uploadingSegment, setUploadingSegment] = useState<number | null>(null);
  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useFocusTrap(!!selectedSegment, () => setSelectedSegment(null), triggerRef);



  const fetchSegments = useCallback(async () => {
    if (!uuid) return;
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/segments`);
      if (!response.ok) {
        throw new Error(`Failed to fetch segments: ${response.status}`);
      }
      const data = await response.json() as { segments: Segment[] };
      setSegments(data.segments || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [uuid]);

  const fetchImageStatuses = useCallback(async (signal?: AbortSignal) => {
    if (!uuid) return {};
    const response = await fetch(`${apiBase}/projects/${uuid}/images/status`, { signal });
    if (response.status === 404) {
      setImageStatuses({});
      return {};
    }
    if (!response.ok) {
      throw new Error(`Failed to fetch image statuses: ${response.status}`);
    }
    const data = await response.json() as Record<string, boolean>;
    const statuses: Record<number, boolean> = {};
    for (const [key, value] of Object.entries(data)) {
      statuses[Number(key)] = value;
    }
    setImageStatuses(statuses);
    return statuses;
  }, [uuid]);

  useEffect(() => {
    fetchSegments().catch((err) => {
      setError(err instanceof Error ? err.message : "Unknown error");
    });
  }, [fetchSegments]);

  useEffect(() => {
    if (segments.length > 0) {
      const controller = new AbortController();
      fetchImageStatuses(controller.signal).catch((err) => {
        if (err.name !== "AbortError") {
          console.error("Failed to fetch image statuses:", err);
        }
      });
      return () => {
        controller.abort();
      };
    }
  }, [segments, fetchImageStatuses]);

  const handleUploadClick = (segmentNumber: number) => {
    const input = fileInputRefs.current[segmentNumber];
    if (input) {
      input.click();
    }
  };

  const handleFileChange = async (segmentNumber: number, file: File | null) => {
    if (!uuid || !file) return;
    if (file.type !== "image/png") {
      setError("Only PNG files are allowed");
      return;
    }
    setUploadingSegment(segmentNumber);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${apiBase}/projects/${uuid}/images/${segmentNumber}`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }
        const statuses = await fetchImageStatuses();
        const allUploaded = segments.length > 0 && segments.every((s) => statuses?.[s.segment_index]);
        if (allUploaded) {
          const stepResp = await fetch(`${apiBase}/projects/${uuid}/step/4`, { method: "PUT" });
          if (!stepResp.ok) {
            console.warn(`PUT /step/4 failed: ${stepResp.status}`);
          }
          onStateChange?.();
        }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadingSegment(null);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[400px]">
        <span className="font-body text-[#8A8A9A] text-lg">Loading segments...</span>
      </div>
    );
  }

  if (error && segments.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px]">
        <span className="font-body text-[#EF4444] text-lg">Error: {error}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {error && segments.length > 0 && (
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 px-4 py-3 font-body text-sm text-[#EF4444]" role="alert" aria-live="assertive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {segments.map((segment) => {
          const hasImage = imageStatuses[segment.segment_index] ?? false;
          return (
            <div
              key={segment.segment_index}
              className="bg-[#1A1A24] border border-[#2A2A35] p-3 flex flex-col gap-3"
              data-testid="segment-cell"
            >
              {/* Segment Number */}
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">
                  Segment {segment.segment_index}
                </span>
                <CopyButton
                  text={segment.segment_prompt}
                  ariaLabel={`Copy prompt for segment ${segment.segment_index}`}
                  disabled={!segment.segment_prompt}
                  title={!segment.segment_prompt ? "No prompt yet" : undefined}
                />
              </div>

              {/* Thumbnail or Placeholder */}
              <div className="relative w-full aspect-video bg-[#2A2A35] border border-[#2A2A35] overflow-hidden">
                {hasImage ? (
                  <img
                    src={`${apiBase}/projects/${uuid}/images/${segment.segment_index}`}
                    alt={`Segment ${segment.segment_index}`}
                    className="w-full h-full object-cover"
                    data-testid="segment-thumbnail"
                  />
                ) : (
                  <div className="flex items-center justify-center w-full h-full bg-[#2A2A35]" data-testid="segment-placeholder">
                    <ImageIcon size={32} weight="regular" className="text-[#5A5A6A]" />
                  </div>
                )}
              </div>

              {/* Hidden File Input */}
              <input
                type="file"
                accept="image/png"
                className="hidden"
                ref={(el) => { fileInputRefs.current[segment.segment_index] = el; }}
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  handleFileChange(segment.segment_index, file).catch(() => {});
                  e.target.value = "";
                }}
              />

              {/* Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleUploadClick(segment.segment_index)}
                  disabled={uploadingSegment === segment.segment_index}
                  className={cn(
                    "flex items-center gap-1.5 flex-1 justify-center px-3 py-2 font-body text-xs font-semibold tracking-wide uppercase",
                    "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
                    "disabled:opacity-50 disabled:cursor-not-allowed"
                  )}
                  data-testid="upload-button"
                >
                  <Upload size={14} weight="regular" />
                  {uploadingSegment === segment.segment_index ? "Uploading..." : "Upload"}
                </button>
                <button
                  onClick={() => {
                    triggerRef.current = document.activeElement as HTMLButtonElement;
                    setSelectedSegment(segment);
                  }}
                  className={cn(
                    "flex items-center gap-1.5 flex-1 justify-center px-3 py-2 font-body text-xs font-semibold tracking-wide uppercase",
                    "bg-[#1E1E28] text-[#06B6D4] border border-[#2A2A35] hover:bg-[#2A2A35]"
                  )}
                  data-testid="details-button"
                >
                  <Info size={14} weight="regular" />
                  Details
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Details Modal */}
      {selectedSegment && (
        <div
          ref={modalRef}
          className="fixed inset-0 bg-[#0F0F14]/80 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedSegment(null)}
          data-testid="details-modal"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="bg-[#1A1A24] border border-[#2A2A35] w-full max-w-[520px] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#2A2A35]">
              <h2 className="font-headline text-xl text-[#E8E8F0]">
                Segment {selectedSegment.segment_index}
              </h2>
              <button
                onClick={() => setSelectedSegment(null)}
                className="flex items-center justify-center w-8 h-8 bg-transparent text-[#8A8A9A] hover:text-[#E8E8F0] hover:bg-[#1A1A24]"
                aria-label="Close details"
              >
                <X size={18} weight="regular" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex flex-col gap-4 p-4">
              <div className="flex flex-col gap-1">
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">Script Line</span>
                <p className="font-body text-sm text-[#E8E8F0]">{selectedSegment.script_line}</p>
              </div>

              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">Segment Prompt</span>
                  <CopyButton
                    text={selectedSegment.segment_prompt}
                    ariaLabel="Copy segment prompt"
                    label="Copy"
                    disabled={!selectedSegment.segment_prompt}
                  />
                </div>
                <p className="font-body text-sm text-[#E8E8F0]">{selectedSegment.segment_prompt}</p>
              </div>

              <div className="flex flex-col gap-1">
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">Characters Present</span>
                <div className="flex flex-wrap gap-2">
                  {selectedSegment.characters_present.length > 0 ? (
                    selectedSegment.characters_present.map((char) => (
                      <span
                        key={char}
                        className="inline-flex items-center px-2 py-1 font-body text-xs bg-[#1E1E28] text-[#06B6D4] border border-[#2A2A35]"
                      >
                        {char}
                      </span>
                    ))
                  ) : (
                    <span className="font-body text-sm text-[#5A5A6A]">None</span>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">Timing</span>
                <p className="font-mono text-sm text-[#E8E8F0]">
                  {formatTime(selectedSegment.start_time)} — {formatTime(selectedSegment.end_time)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
