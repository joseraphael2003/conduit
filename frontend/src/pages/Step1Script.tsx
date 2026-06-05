import { useState, useEffect, useRef, useMemo } from "react";
import { cn } from "@/lib/utils";
import { AmberBar } from "@/components/AmberBar";
import {
  Upload,
  FileText,
  CaretDown,
  CaretUp,
  Check,
  X,
  Warning,
  ArrowClockwise,
  Article,
  GitDiff,
} from "@phosphor-icons/react";
import { useDiff } from "@/hooks/useDiff";
import { useTranscript } from "@/hooks/useTranscript";

function isValidAudioFile(file: File): boolean {
  const validTypes = [
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
  ];
  const validExtensions = [".mp3", ".wav", ".m4a"];
  return (
    validTypes.includes(file.type) ||
    validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))
  );
}

interface Step1ScriptProps {
  onStep1Ready?: (data: { hasTranscript: boolean; hasScript: boolean; fidelity: number | null }) => void;
}

export function Step1Script({ onStep1Ready }: Step1ScriptProps) {
  const [script, setScript] = useState<string>("");
  const [showScript, setShowScript] = useState(false);
  const [approvedChanges, setApprovedChanges] = useState<Set<number>>(new Set());
  const [rejectedChanges, setRejectedChanges] = useState<Set<number>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropzoneRef = useRef<HTMLDivElement>(null);

  const { computeDiff } = useDiff();
  const {
    transcript,
    fetchTranscript,
    handleUpload,
    loading,
    error,
    setError,
    uploading,
    uploadProgress,
  } = useTranscript();

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files[0];
    if (file && isValidAudioFile(file)) {
      handleUpload(file);
    } else {
      setError("Please upload an MP3, WAV, or M4A file.");
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (isValidAudioFile(file)) {
        handleUpload(file);
      } else {
        setError("Please upload an MP3, WAV, or M4A file.");
      }
    }
    e.target.value = "";
  };

  const handleApprove = (index: number) => {
    setApprovedChanges((prev) => new Set(prev).add(index));
    setRejectedChanges((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return next;
    });
  };

  const handleReject = (index: number) => {
    setRejectedChanges((prev) => new Set(prev).add(index));
    setApprovedChanges((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return next;
    });
  };

  const handleApproveRemaining = () => {
    diffBlocks.forEach((block, index) => {
      if (block.type !== "equal" && !approvedChanges.has(index) && !rejectedChanges.has(index)) {
        handleApprove(index);
      }
    });
  };

  const diffBlocks = script ? computeDiff(transcript, script) : [];
  const hasChanges = diffBlocks.some((b) => b.type !== "equal");
  const unreviewedCount = diffBlocks.filter(
    (b, i) => b.type !== "equal" && !approvedChanges.has(i) && !rejectedChanges.has(i)
  ).length;

  const fidelity = useMemo(() => {
    if (!script || !script.trim()) return null;

    const countNonWhitespace = (words: string[]) =>
      words.filter((w) => w.trim().length > 0).length;

    const totalScriptWords = diffBlocks.reduce(
      (sum, block) => sum + countNonWhitespace(block.newWords),
      0
    );

    if (totalScriptWords === 0) return null;

    const matchedWords = diffBlocks.reduce((sum, block, index) => {
      if (block.type === "equal" || approvedChanges.has(index)) {
        return sum + countNonWhitespace(block.newWords);
      }
      return sum;
    }, 0);

    return (matchedWords / totalScriptWords) * 100;
  }, [diffBlocks, approvedChanges, script]);

  useEffect(() => {
    if (onStep1Ready) {
      onStep1Ready({
        hasTranscript: transcript.trim().length > 0,
        hasScript: script.trim().length > 0,
        fidelity,
      });
    }
  }, [transcript, script, fidelity, onStep1Ready]);

  return (
    <div className="p-6 max-w-[1200px] mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-headline text-2xl text-[#E8E8F0] mb-1">
            Script
          </h2>
          <p className="font-body text-sm text-[#8A8A9A]">
            Upload your voiceover and review the transcript against your original script.
          </p>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-3 bg-[#EF4444]/10 border border-[#EF4444]/20 p-3" role="alert" aria-live="assertive">
          <Warning size={20} weight="regular" className="text-[#EF4444] shrink-0" />
          <span className="font-body text-sm text-[#EF4444] flex-1">{error}</span>
          <button
            onClick={() => {
              setError(null);
              fetchTranscript();
            }}
            className="flex items-center gap-1 px-3 py-1.5 font-body text-xs font-semibold tracking-wide uppercase bg-[#EF4444]/20 text-[#EF4444] hover:bg-[#EF4444]/30"
          >
            <ArrowClockwise size={14} weight="regular" />
            Retry
          </button>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        ref={dropzoneRef}
        data-testid="voiceover-dropzone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        tabIndex={0}
        role="button"
        aria-label="Upload voiceover file"
        className={cn(
          "w-full h-[200px] border-2 border-dashed border-[#2A2A35] bg-[#0A0A0F]",
          "flex flex-col items-center justify-center gap-3 cursor-pointer",
          "hover:border-[#F0A040] hover:bg-[#1A1A24] transition-colors"
        )}
      >
        <input
          type="file"
          accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a"
          className="hidden"
          ref={fileInputRef}
          onChange={handleFileChange}
        />
        {uploading ? (
          <>
            <AmberBar />
            <span className="font-body text-sm text-[#8A8A9A]">Uploading voiceover...</span>
          </>
        ) : (
          <>
            <Upload size={32} weight="regular" className="text-[#8A8A9A]" />
            <div className="flex flex-col items-center gap-1">
              <span className="font-body text-sm text-[#E8E8F0]">
                Click or drag to upload voiceover
              </span>
              <span className="font-body text-xs text-[#5A5A6A]">
                MP3, WAV, or M4A
              </span>
            </div>
          </>
        )}
      </div>

      {/* Progress Bar */}
      {uploading && (
        <div className="w-full">
          <div className="flex items-center justify-between mb-1">
            <span className="font-body text-xs text-[#8A8A9A]">Upload progress</span>
            <span className="font-body text-xs text-[#E8E8F0]">{uploadProgress}%</span>
          </div>
          <div className="w-full h-2 bg-[#1A1A24] border border-[#2A2A35]">
            <div
              className="h-full bg-[#F0A040] transition-all duration-300 progress-bar-fill"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Original Script — Collapsible */}
      <div className="border border-[#2A2A35] bg-[#0A0A0F]">
        <button
          onClick={() => setShowScript((prev) => !prev)}
          aria-expanded={showScript}
          aria-controls="original-script-panel"
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1A1A24] transition-colors"
        >
          <div className="flex items-center gap-2">
            <Article size={18} weight="regular" className="text-[#8A8A9A]" />
            <span className="font-body text-sm text-[#E8E8F0]">Original Script</span>
          </div>
          {showScript ? (
            <CaretUp size={16} weight="regular" className="text-[#8A8A9A]" />
          ) : (
            <CaretDown size={16} weight="regular" className="text-[#8A8A9A]" />
          )}
        </button>
        {showScript && (
          <div id="original-script-panel" className="px-4 pb-4">
            <textarea
              value={script}
              onChange={(e) => setScript(e.target.value)}
              placeholder="Paste your original script here to compare with the transcript..."
              className={cn(
                "w-full h-[200px] bg-[#0F0F14] border border-[#2A2A35] p-3",
                "font-mono text-sm text-[#E8E8F0] resize-none",
                "focus:border-[#F0A040] focus:outline-none"
              )}
              data-testid="original-script-input"
            />
          </div>
        )}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center h-[200px] border border-[#2A2A35] bg-[#0A0A0F]">
          <AmberBar />
          <span className="font-body text-[#8A8A9A] ml-3">
            Loading transcript...
          </span>
        </div>
      )}

      {/* Transcript Display */}
      {!loading && transcript && !script && (
        <div
          className="border border-[#2A2A35] bg-[#0A0A0F] flex flex-col"
          data-testid="transcript-display"
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[#2A2A35]">
            <FileText size={18} weight="regular" className="text-[#8A8A9A]" />
            <span className="font-body text-sm font-semibold text-[#E8E8F0]">Transcript</span>
            <span className="font-body text-xs text-[#5A5A6A] ml-auto">
              {transcript.split(/\s+/).filter(Boolean).length} words
            </span>
          </div>
          <div className="p-4 overflow-y-auto" style={{ height: "600px" }}>
            <p className="font-body text-sm text-[#E8E8F0] whitespace-pre-wrap leading-relaxed">
              {transcript}
            </p>
          </div>
        </div>
      )}

      {/* AI Diff UI */}
      {!loading && transcript && script && (
        <div
          className="border border-[#2A2A35] bg-[#0A0A0F] flex flex-col"
          data-testid="diff-ui"
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[#2A2A35]">
            <GitDiff size={18} weight="regular" className="text-[#8A8A9A]" />
            <span className="font-body text-sm font-semibold text-[#E8E8F0]">
              AI Diff
            </span>
            <div className="flex items-center gap-2 ml-auto">
              <button
                onClick={handleApproveRemaining}
                disabled={unreviewedCount === 0}
                data-testid="approve-remaining"
                className={cn(
                  "flex items-center gap-1 px-4 py-2 font-body text-xs font-semibold tracking-wide uppercase",
                  "bg-transparent text-[#8A8A9A] hover:bg-[#1E1E28] hover:text-[#E8E8F0]",
                  "disabled:text-[#5A5A6A] disabled:hover:bg-transparent disabled:cursor-not-allowed"
                )}
              >
                <Check size={12} weight="regular" />
                Approve Remaining
              </button>
              {fidelity !== null && (
                <span
                  data-testid="fidelity-badge"
                  className={cn(
                    "px-2 py-1 font-body text-[10px] font-semibold uppercase tracking-wide",
                    fidelity >= 95
                      ? "bg-[#0F2818] text-[#22C55E]"
                      : fidelity >= 80
                        ? "bg-[#2A2500] text-[#EAB308]"
                        : "bg-[#2A1010] text-[#EF4444]"
                  )}
                >
                  {Math.round(fidelity)}%
                </span>
              )}
              <span className="font-body text-xs text-[#5A5A6A]">
                {hasChanges ? `${diffBlocks.filter((b) => b.type !== "equal").length} changes` : "No changes"}
              </span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto" style={{ maxHeight: "600px" }}>
            {/* Diff Header */}
            <div className="grid grid-cols-2 border-b border-[#2A2A35]">
              <div className="px-4 py-2 border-r border-[#2A2A35]">
                <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Transcript
                </span>
              </div>
              <div className="px-4 py-2">
                <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Script
                </span>
              </div>
            </div>

            {/* Diff Rows */}
            <div className="flex flex-col">
              {diffBlocks.map((block, index) => {
                const isApproved = approvedChanges.has(index);
                const isRejected = rejectedChanges.has(index);
                const isChange = block.type !== "equal";

                return (
                  <div
                    key={index}
                    className={cn(
                      "grid grid-cols-2",
                      isChange && "border-b border-[#2A2A35]"
                    )}
                    data-testid={isChange ? "diff-change" : undefined}
                  >
                    {/* Left — Transcript */}
                    <div
                      className={cn(
                        "px-4 py-2 border-r border-[#2A2A35] font-body text-sm leading-relaxed",
                        block.type === "delete" || block.type === "change"
                          ? "bg-[#EF4444]/10"
                          : "bg-[#0A0A0F]"
                      )}
                    >
                      {block.oldWords.length > 0 ? (
                        <span
                          className={cn(
                            "whitespace-pre-wrap",
                            block.type === "delete" || block.type === "change"
                              ? "text-[#EF4444]"
                              : "text-[#E8E8F0]"
                          )}
                        >
                          {block.oldWords.join("")}
                        </span>
                      ) : (
                        <span className="text-[#5A5A6A]">—</span>
                      )}
                    </div>

                    {/* Right — Script */}
                    <div
                      className={cn(
                        "px-4 py-2 font-body text-sm leading-relaxed",
                        block.type === "insert" || block.type === "change"
                          ? "bg-[#22C55E]/10"
                          : "bg-[#0A0A0F]"
                      )}
                    >
                      {block.newWords.length > 0 ? (
                        <span
                          className={cn(
                            "whitespace-pre-wrap",
                            block.type === "insert" || block.type === "change"
                              ? "text-[#22C55E]"
                              : "text-[#E8E8F0]"
                          )}
                        >
                          {block.newWords.join("")}
                        </span>
                      ) : (
                        <span className="text-[#5A5A6A]">—</span>
                      )}
                    </div>

                    {/* Approve / Reject Buttons */}
                    {isChange && (
                      <div className="col-span-2 flex items-center gap-2 px-4 py-2 border-t border-[#2A2A35] bg-[#0F0F14]">
                        <button
                          onClick={() => handleApprove(index)}
                          data-testid="approve-button"
                          className={cn(
                            "flex items-center gap-1 px-3 py-1 font-body text-xs font-semibold tracking-wide uppercase",
                            isApproved
                              ? "bg-[#22C55E] text-[#0F0F14]"
                              : "bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20 hover:bg-[#22C55E]/20"
                          )}
                        >
                          <Check size={12} weight="regular" />
                          {isApproved ? "Approved" : "Approve"}
                        </button>
                        <button
                          onClick={() => handleReject(index)}
                          data-testid="reject-button"
                          className={cn(
                            "flex items-center gap-1 px-3 py-1 font-body text-xs font-semibold tracking-wide uppercase",
                            isRejected
                              ? "bg-[#EF4444] text-[#0F0F14]"
                              : "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20 hover:bg-[#EF4444]/20"
                          )}
                        >
                          <X size={12} weight="regular" />
                          {isRejected ? "Rejected" : "Reject"}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Empty state — no transcript yet */}
      {!loading && !transcript && !uploading && (
        <div className="flex flex-col items-center justify-center h-[300px] border border-[#2A2A35] bg-[#0A0A0F] gap-4">
          <FileText size={40} weight="regular" className="text-[#5A5A6A]" />
          <p className="font-body text-sm text-[#8A8A9A] text-center max-w-[360px]">
            No transcript yet. Upload a voiceover file to generate a transcript.
          </p>
        </div>
      )}
    </div>
  );
}
