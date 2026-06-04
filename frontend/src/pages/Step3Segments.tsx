import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { SkeletonTable } from "@/components/SkeletonTable";
import { AmberBar } from "@/components/AmberBar";
import {
  Scissors,
  ArrowsMerge,
  Wrench,
  PencilSimple,
  Warning,
  ArrowClockwise,
  Check,
} from "@phosphor-icons/react";

interface Segment {
  segment_index: number;
  script_line: string;
  start_time: number;
  end_time: number;
  duration: number;
  prompt: string;
  characters: string[];
}

export function Step3Segments() {
  const { uuid } = useParams<{ uuid: string }>();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [breakdownDone, setBreakdownDone] = useState(false);
  const [promptsGenerated, setPromptsGenerated] = useState(false);
  const [splitPoints, setSplitPoints] = useState<Record<number, number>>({});
  const [savingPrompt, setSavingPrompt] = useState<Record<number, boolean>>({});
  const [promptErrors, setPromptErrors] = useState<Record<number, string | null>>({});

  const loadSegments = useCallback(async () => {
    if (!uuid) return;
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments`
      );
      if (!response.ok) {
        if (response.status === 404) {
          return;
        }
        throw new Error(`Failed to fetch segments: ${response.status}`);
      }
      const data = await response.json();
      if (data.segments && data.segments.length > 0) {
        setSegments(data.segments);
        setBreakdownDone(true);
      }
    } catch {
      // Silent fail on initial load
    }
  }, [uuid]);

  useEffect(() => {
    loadSegments();
  }, [loadSegments]);

  const handleBreakdown = async () => {
    if (!uuid) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments/breakdown`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );
      if (!response.ok) {
        throw new Error(`Breakdown failed: ${response.status}`);
      }
      const data = await response.json();
      setSegments(data.segments || []);
      setBreakdownDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error during breakdown");
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePrompts = async () => {
    if (!uuid) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments/prompts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );
      if (!response.ok) {
        throw new Error(`Prompt generation failed: ${response.status}`);
      }
      const data = await response.json();
      setSegments(data.segments || []);
      setPromptsGenerated(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error during prompt generation");
    } finally {
      setLoading(false);
    }
  };

  const handlePromptChange = (index: number, newPrompt: string) => {
    setSegments((prev) =>
      prev.map((seg, i) => (i === index ? { ...seg, prompt: newPrompt } : seg))
    );
  };

  const handlePromptBlur = async (index: number) => {
    if (!uuid) return;
    const segment = segments[index];
    if (!segment) return;

    setSavingPrompt((prev) => ({ ...prev, [index]: true }));
    setPromptErrors((prev) => ({ ...prev, [index]: null }));

    try {
      // Fetch full segment list from server
      const getResponse = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments`
      );
      if (!getResponse.ok) {
        throw new Error(`Fetch failed: ${getResponse.status}`);
      }
      const fullData = await getResponse.json();
      const fullSegments = fullData.segments || [];

      // Apply local edit to the matching segment
      const updatedSegments = fullSegments.map((seg: any) =>
        seg.segment_index === segment.segment_index
          ? { ...seg, prompt: segment.prompt }
          : seg
      );

      // PUT complete list
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segments: updatedSegments }),
        }
      );
      if (!response.ok) {
        throw new Error(`Save failed: ${response.status}`);
      }
    } catch (err) {
      setPromptErrors((prev) => ({
        ...prev,
        [index]: err instanceof Error ? err.message : "Save failed",
      }));
    } finally {
      setSavingPrompt((prev) => ({ ...prev, [index]: false }));
    }
  };

  const handleSplitPointChange = (segmentIndex: number, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      setSplitPoints((prev) => ({ ...prev, [segmentIndex]: num }));
    }
  };

  const handleSplit = async (segmentIndex: number) => {
    if (!uuid) return;
    const segment = segments[segmentIndex];
    if (!segment) return;

    const splitPoint =
      splitPoints[segmentIndex] ?? segment.start_time + segment.duration / 2;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments/${segmentIndex}/split`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ split_point: splitPoint }),
        }
      );
      if (!response.ok) {
        throw new Error(`Split failed: ${response.status}`);
      }
      const data = await response.json();
      setSegments(data.segments || []);
      setSplitPoints((prev) => {
        const next = { ...prev };
        delete next[segmentIndex];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error during split");
    } finally {
      setLoading(false);
    }
  };

  const handleMerge = async (segmentIndex: number) => {
    if (!uuid) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/projects/${uuid}/segments/${segmentIndex}/merge`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );
      if (!response.ok) {
        throw new Error(`Merge failed: ${response.status}`);
      }
      const data = await response.json();
      setSegments(data.segments || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error during merge");
    } finally {
      setLoading(false);
    }
  };

  if (!uuid) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="font-body text-[#EF4444]">No project UUID found</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-3 bg-[#EF4444]/10 border border-[#EF4444]/20 p-3" role="alert" aria-live="assertive">
          <Warning size={20} weight="regular" className="text-[#EF4444] shrink-0" />
          <span className="font-body text-sm text-[#EF4444] flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="flex items-center gap-1 px-3 py-1.5 font-body text-xs font-semibold tracking-wide uppercase bg-[#EF4444]/20 text-[#EF4444] hover:bg-[#EF4444]/30"
          >
            <ArrowClockwise size={14} weight="regular" />
            Retry
          </button>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleBreakdown}
          disabled={loading}
          className={cn(
            "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {loading ? (
            <AmberBar />
          ) : (
            <Wrench size={16} weight="regular" />
          )}
          Generate Segments
        </button>

        {breakdownDone && (
          <button
            onClick={handleGeneratePrompts}
            disabled={loading}
            className={cn(
              "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
              "bg-[#1E1E28] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#2A2A35]",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {loading ? (
              <AmberBar />
            ) : (
              <PencilSimple size={16} weight="regular" />
            )}
            Generate Prompts
          </button>
        )}
      </div>

      {/* Segment Loading */}
      {loading && segments.length === 0 && (
        <div className="flex-1 overflow-auto">
          <SkeletonTable columns={7} />
        </div>
      )}

      {/* Segment Table */}
      {segments.length > 0 && (
        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#1A1A24] border-b border-[#2A2A35]">
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Segment #
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Script Line
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Start → End
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Duration
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Prompt
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Characters
                </th>
                <th className="px-3 py-2 text-left font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {segments.map((segment, index) => (
                <tr
                  key={segment.segment_index}
                  className="border-b border-[#2A2A35] hover:bg-[#1A1A24]/50"
                >
                  <td className="px-3 py-3 font-mono text-sm text-[#E8E8F0]">
                    {segment.segment_index}
                  </td>
                  <td className="px-3 py-3 font-body text-sm text-[#E8E8F0] max-w-[200px] truncate">
                    {segment.script_line}
                  </td>
                  <td className="px-3 py-3 font-mono text-sm text-[#8A8A9A]">
                    {segment.start_time.toFixed(1)}s → {segment.end_time.toFixed(1)}s
                  </td>
                  <td className="px-3 py-3 font-mono text-sm text-[#8A8A9A]">
                    {segment.duration.toFixed(1)}s
                  </td>
                  <td className="px-3 py-3">
                    <div className="relative">
                      <textarea
                        value={segment.prompt || ""}
                        onChange={(e) => handlePromptChange(index, e.target.value)}
                        onBlur={() => handlePromptBlur(index)}
                        className={cn(
                          "w-full min-w-[200px] bg-[#0A0A0F] border border-[#2A2A35] p-2 font-body text-sm text-[#E8E8F0]",
                          "focus:border-[#F0A040] focus:outline-none",
                          "resize-y min-h-[60px]"
                        )}
                        placeholder="Enter prompt..."
                        rows={2}
                      />
                      {savingPrompt[index] && (
                        <div className="absolute top-2 right-2">
                          <AmberBar />
                        </div>
                      )}
                      {promptErrors[index] && (
                        <span className="absolute bottom-0 left-0 right-0 text-[10px] text-[#EF4444] bg-[#EF4444]/10 px-2 py-0.5">
                          {promptErrors[index]}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      {segment.characters && segment.characters.length > 0 ? (
                        segment.characters.map((char) => (
                          <span
                            key={char}
                            className="font-mono text-xs text-[#06B6D4] bg-[#06B6D4]/10 px-1.5 py-0.5"
                          >
                            @{char}
                          </span>
                        ))
                      ) : (
                        <span className="font-mono text-xs text-[#5A5A6A]">—</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          step="0.1"
                          value={
                            splitPoints[index] !== undefined
                              ? splitPoints[index]
                              : (segment.start_time + segment.duration / 2).toFixed(1)
                          }
                          onChange={(e) => handleSplitPointChange(index, e.target.value)}
                          className="w-[80px] bg-[#0A0A0F] border border-[#2A2A35] p-1 font-mono text-xs text-[#E8E8F0] focus:border-[#F0A040] focus:outline-none"
                          placeholder="Split at"
                        />
                        <button
                          onClick={() => handleSplit(index)}
                          disabled={loading}
                          className={cn(
                            "flex items-center gap-1 px-2 py-1 font-body text-xs font-semibold tracking-wide uppercase",
                            "bg-[#1E1E28] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#2A2A35]",
                            "disabled:opacity-50 disabled:cursor-not-allowed"
                          )}
                          title="Split segment at selected point"
                        >
                          <Scissors size={14} weight="regular" />
                          Split
                        </button>
                      </div>
                      <button
                        onClick={() => handleMerge(index)}
                        disabled={loading || index === segments.length - 1}
                        className={cn(
                          "flex items-center gap-1 px-2 py-1 font-body text-xs font-semibold tracking-wide uppercase",
                          "bg-[#1E1E28] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#2A2A35]",
                          "disabled:opacity-50 disabled:cursor-not-allowed"
                        )}
                        title="Merge with next segment"
                      >
                        <ArrowsMerge size={14} weight="regular" />
                        Merge
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Prompts Generated Banner */}
      {promptsGenerated && (
        <div className="flex items-center gap-3 bg-[#22C55E]/10 border border-[#22C55E]/20 p-3" role="alert" aria-live="assertive">
          <Check size={20} weight="regular" className="text-[#22C55E] shrink-0" />
          <span className="font-body text-sm text-[#22C55E]">
            Prompts generated successfully.
          </span>
        </div>
      )}

      {/* Empty state */}
      {segments.length === 0 && !loading && !error && (
        <div className="flex flex-col items-center justify-center flex-1 gap-4">
          <div className="relative w-[80px] h-[60px]">
            <div className="absolute top-0 left-0 w-[60px] h-[40px] bg-[#1E1E28] border border-[#5A5A6A]" />
            <div className="absolute top-[15px] left-[15px] w-[60px] h-[40px] bg-[#5A5A6A] border border-[#1E1E28]" />
          </div>
          <p className="font-body text-sm text-[#8A8A9A] text-center max-w-[360px]">
            No segments yet. Click "Generate Segments" to break down the script into segments.
          </p>
        </div>
      )}
    </div>
  );
}
