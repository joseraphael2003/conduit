import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { SkeletonTable } from "@/components/SkeletonTable";
import { AmberBar } from "@/components/AmberBar";
import {
  User,
  Copy,
  Code,
  ArrowClockwise,
  Sparkle,
  PencilSimple,
} from "@phosphor-icons/react";
import { apiBase } from "@/config";

interface Character {
  name: string;
  type: string;
  importance: string;
  description: string;
  front_profile_prompt?: string;
  turnaround_reference_prompt?: string;
}

interface ApiResponse {
  characters?: Character[];
}

export function Step2Characters() {
  const { uuid } = useParams<{ uuid: string }>();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [generatingPrompts, setGeneratingPrompts] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasEdits, setHasEdits] = useState(false);
  const [showJson, setShowJson] = useState<Record<string, boolean>>({});
  const [copiedMap, setCopiedMap] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!uuid) return;
    const fetchCharacters = async () => {
      try {
        const response = await fetch(
          `${apiBase}/projects/${uuid}/characters`
        );
        if (!response.ok) return;
        const data = (await response.json()) as ApiResponse;
        if (data.characters) {
          setCharacters(data.characters);
        }
      } catch {
        // silent fail on initial load
      }
    };
    fetchCharacters();
  }, [uuid]);

  const handleExtract = async () => {
    if (!uuid) return;
    setExtracting(true);
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/projects/${uuid}/characters/extract`,
        { method: "POST" }
      );
      if (!response.ok) {
        throw new Error(`Extraction failed: ${response.status}`);
      }
      const data = (await response.json()) as ApiResponse;
      setCharacters(data.characters ?? []);
      setHasEdits(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setExtracting(false);
    }
  };

  const handleDescriptionChange = (index: number, value: string) => {
    setCharacters((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], description: value };
      return next;
    });
    setHasEdits(true);
  };

  const handleSave = async () => {
    if (!uuid) return;
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/projects/${uuid}/characters`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ characters }),
        }
      );
      if (!response.ok) {
        throw new Error(`Save failed: ${response.status}`);
      }
      setHasEdits(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePrompts = async () => {
    if (!uuid) return;
    setGeneratingPrompts(true);
    setError(null);
    try {
      // Save first so the backend has the latest descriptions
      const saveResponse = await fetch(
        `${apiBase}/projects/${uuid}/characters`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ characters }),
        }
      );
      if (!saveResponse.ok) {
        throw new Error(`Save failed: ${saveResponse.status}`);
      }
      setHasEdits(false);

      const response = await fetch(
        `${apiBase}/projects/${uuid}/characters/prompts`,
        { method: "POST" }
      );
      if (!response.ok) {
        throw new Error(`Prompt generation failed: ${response.status}`);
      }
      const data = (await response.json()) as ApiResponse;
      setCharacters(data.characters ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setGeneratingPrompts(false);
    }
  };

  const handleCopy = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMap((prev) => ({ ...prev, [key]: true }));
      setTimeout(() => {
        setCopiedMap((prev) => ({ ...prev, [key]: false }));
      }, 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopiedMap((prev) => ({ ...prev, [key]: true }));
      setTimeout(() => {
        setCopiedMap((prev) => ({ ...prev, [key]: false }));
      }, 2000);
    }
  };

  const toggleJson = (name: string) => {
    setShowJson((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="font-headline text-2xl text-[#E8E8F0] mb-1">
            Characters
          </h2>
          <p className="font-body text-sm text-[#8A8A9A]">
            Extract characters from your script and generate image prompts.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-body text-xs text-[#8A8A9A]">
            AI Model:{" "}
            <span className="text-[#E8E8F0]">GPT-4</span>
          </span>
          <button
            onClick={handleExtract}
            disabled={extracting}
            className={cn(
              "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
              "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {extracting ? (
              <AmberBar />
            ) : (
              <User size={16} weight="regular" />
            )}
            Extract Characters
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-6 p-4 border border-[#EF4444] bg-[#EF4444]/10 flex items-start justify-between gap-4" role="alert" aria-live="assertive">
          <div className="flex items-center gap-2">
            <PencilSimple size={16} weight="regular" className="text-[#EF4444] shrink-0" />
            <span className="font-body text-sm text-[#EF4444]">{error}</span>
          </div>
          <button
            onClick={handleExtract}
            className="flex items-center gap-1 font-body text-xs text-[#8A8A9A] hover:text-[#E8E8F0] shrink-0"
          >
            <ArrowClockwise size={12} weight="regular" />
            Retry
          </button>
        </div>
      )}

      {/* Extraction Loading */}
      {extracting && (
        <div className="mb-6">
          <SkeletonTable columns={4} />
        </div>
      )}

      {/* Character Table */}
      {characters.length > 0 && !extracting && (
        <div className="mb-6">
          <div className="overflow-x-auto border border-[#2A2A35]">
            <table className="w-full">
              <thead className="bg-[#1A1A24]">
                <tr>
                  <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                    Name
                  </th>
                  <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                    Type
                  </th>
                  <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                    Importance
                  </th>
                  <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody>
                {characters.map((char, index) => (
                  <tr
                    key={char.name}
                    className="border-b border-[#2A2A35] last:border-b-0"
                  >
                    <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                      {char.name}
                    </td>
                    <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                      <span className="inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border text-[#06B6D4] border-[#06B6D4]/20 bg-[#06B6D4]/10">
                        {char.type}
                      </span>
                    </td>
                    <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                      <span
                        className={cn(
                          "inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border",
                          char.importance === "main"
                            ? "text-[#F0A040] border-[#F0A040]/20 bg-[#F0A040]/10"
                            : "text-[#5A5A6A] border-[#5A5A6A]/20 bg-[#5A5A6A]/10"
                        )}
                      >
                        {char.importance}
                      </span>
                    </td>
                    <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 min-w-[300px]">
                      <textarea
                        value={char.description}
                        onChange={(e) =>
                          handleDescriptionChange(index, e.target.value)
                        }
                        className="w-full bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 resize-none focus:border-[#F0A040] focus:outline-none"
                        rows={3}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={!hasEdits || saving}
              className={cn(
                "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
                "bg-[#1A1A24] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#1E1E28]",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {saving ? (
                <AmberBar />
              ) : (
                <PencilSimple size={16} weight="regular" />
              )}
              Save Changes
            </button>
            <button
              onClick={handleGeneratePrompts}
              disabled={!hasEdits || generatingPrompts}
              data-testid="generate-prompts-button"
              className={cn(
                "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
                "bg-[#06B6D4] text-[#0F0F14] hover:bg-[#06B6D4]/80",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {generatingPrompts ? (
                <AmberBar />
              ) : (
                <Sparkle size={16} weight="regular" />
              )}
              Generate Prompts
            </button>
          </div>
        </div>
      )}

      {/* Prompt Cards */}
      {characters.some((c) => c.front_profile_prompt) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {characters.map((char) => (
            <div
              key={char.name}
              className="border border-[#2A2A35] bg-[#0F0F14] p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-headline text-lg text-[#E8E8F0]">
                    {char.name}
                  </h3>
                  <span className="inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border text-[#06B6D4] border-[#06B6D4]/20 bg-[#06B6D4]/10">
                    {char.type}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border",
                      char.importance === "main"
                        ? "text-[#F0A040] border-[#F0A040]/20 bg-[#F0A040]/10"
                        : "text-[#5A5A6A] border-[#5A5A6A]/20 bg-[#5A5A6A]/10"
                    )}
                  >
                    {char.importance}
                  </span>
                </div>
                <button
                  onClick={() => toggleJson(char.name)}
                  className="flex items-center gap-1 text-[#8A8A9A] hover:text-[#E8E8F0] font-body text-xs"
                  aria-label="Toggle JSON"
                  aria-expanded={!!showJson[char.name]}
                  aria-controls={`json-panel-${char.name}`}
                >
                  <Code size={16} weight="regular" />
                  JSON
                </button>
              </div>

              {showJson[char.name] ? (
                <pre id={`json-panel-${char.name}`} className="font-mono text-xs text-[#8A8A9A] bg-[#1A1A24] p-3 overflow-auto border border-[#2A2A35]">
                  {JSON.stringify(char, null, 2)}
                </pre>
              ) : (
                <div id={`json-panel-${char.name}`} className="flex flex-col gap-3">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                        Front Profile Prompt
                      </span>
                      <button
                        onClick={() =>
                          handleCopy(
                            char.front_profile_prompt ?? "",
                            `front-${char.name}`
                          )
                        }
                        className="flex items-center gap-1 text-[#8A8A9A] hover:text-[#E8E8F0] font-body text-xs"
                        aria-label={`Copy front profile prompt for ${char.name}`}
                      >
                        <Copy size={12} weight="regular" />
                        {copiedMap[`front-${char.name}`] ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p className="font-body text-sm text-[#E8E8F0] bg-[#1A1A24] p-3 border border-[#2A2A35] whitespace-pre-wrap">
                      {char.front_profile_prompt}
                    </p>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A]">
                        Turnaround Reference Prompt
                      </span>
                      <button
                        onClick={() =>
                          handleCopy(
                            char.turnaround_reference_prompt ?? "",
                            `turn-${char.name}`
                          )
                        }
                        className="flex items-center gap-1 text-[#8A8A9A] hover:text-[#E8E8F0] font-body text-xs"
                        aria-label={`Copy turnaround reference prompt for ${char.name}`}
                      >
                        <Copy size={12} weight="regular" />
                        {copiedMap[`turn-${char.name}`] ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p className="font-body text-sm text-[#E8E8F0] bg-[#1A1A24] p-3 border border-[#2A2A35] whitespace-pre-wrap">
                      {char.turnaround_reference_prompt}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
