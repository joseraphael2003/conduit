import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Upload, Info, Image as ImageIcon, X } from "@phosphor-icons/react";

interface Segment {
  segment_number: number;
  script_line: string;
  segment_prompt: string;
  characters_present: string[];
  start_time: number;
  end_time: number;
}

export function Step4Images() {
  const { uuid } = useParams<{ uuid: string }>();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [imageStatuses, setImageStatuses] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  const [uploadingSegment, setUploadingSegment] = useState<number | null>(null);
  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const apiBase = "http://localhost:8000/api/v1";

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

  const checkImageStatus = useCallback(async (segmentNumber: number) => {
    if (!uuid) return;
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/images/${segmentNumber}`);
      setImageStatuses(prev => ({
        ...prev,
        [segmentNumber]: response.ok
      }));
    } catch {
      setImageStatuses(prev => ({
        ...prev,
        [segmentNumber]: false
      }));
    }
  }, [uuid]);

  useEffect(() => {
    fetchSegments();
  }, [fetchSegments]);

  useEffect(() => {
    if (segments.length > 0) {
      segments.forEach(seg => {
        checkImageStatus(seg.segment_number);
      });
    }
  }, [segments, checkImageStatus]);

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
      await checkImageStatus(segmentNumber);
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
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/20 px-4 py-3 font-body text-sm text-[#EF4444]">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {segments.map((segment) => {
          const hasImage = imageStatuses[segment.segment_number] ?? false;
          return (
            <div
              key={segment.segment_number}
              className="bg-[#1A1A24] border border-[#2A2A35] p-3 flex flex-col gap-3"
              data-testid="segment-cell"
            >
              {/* Segment Number */}
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">
                  Segment {segment.segment_number}
                </span>
              </div>

              {/* Thumbnail or Placeholder */}
              <div className="relative w-full aspect-video bg-[#2A2A35] border border-[#2A2A35] overflow-hidden">
                {hasImage ? (
                  <img
                    src={`${apiBase}/projects/${uuid}/images/${segment.segment_number}`}
                    alt={`Segment ${segment.segment_number}`}
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
                ref={(el) => { fileInputRefs.current[segment.segment_number] = el; }}
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  handleFileChange(segment.segment_number, file).catch(() => {});
                  e.target.value = "";
                }}
              />

              {/* Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleUploadClick(segment.segment_number)}
                  disabled={uploadingSegment === segment.segment_number}
                  className={cn(
                    "flex items-center gap-1.5 flex-1 justify-center px-3 py-2 font-body text-xs font-semibold tracking-wide uppercase",
                    "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
                    "disabled:opacity-50 disabled:cursor-not-allowed"
                  )}
                  data-testid="upload-button"
                >
                  <Upload size={14} weight="regular" />
                  {uploadingSegment === segment.segment_number ? "Uploading..." : "Upload"}
                </button>
                <button
                  onClick={() => setSelectedSegment(segment)}
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
          className="fixed inset-0 bg-[#0F0F14]/80 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedSegment(null)}
          data-testid="details-modal"
        >
          <div
            className="bg-[#1A1A24] border border-[#2A2A35] w-full max-w-[520px] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#2A2A35]">
              <h2 className="font-headline text-xl text-[#E8E8F0]">
                Segment {selectedSegment.segment_number}
              </h2>
              <button
                onClick={() => setSelectedSegment(null)}
                className="flex items-center justify-center w-8 h-8 text-[#8A8A9A] hover:text-[#E8E8F0] hover:bg-[#1E1E28]"
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
                <span className="font-mono text-xs text-[#8A8A9A] uppercase tracking-wide">Segment Prompt</span>
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
