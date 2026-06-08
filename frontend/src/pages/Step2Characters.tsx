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
  Plus,
  Trash,
  Clock,
} from "@phosphor-icons/react";
import { apiBase } from "@/config";

interface Character {
  name: string;
  type: "speaking" | "creature" | "npc_entity";
  importance: "major" | "minor";
  description: string;
  front_profile_prompt?: string;
  turnaround_prompt?: string;
  base_name?: string;
  version_label?: string;
  version_index?: number;
  appears_from?: string;
  identity_anchor?: string;
}

interface ApiResponse {
  characters?: Character[];
}

interface ProjectResponse {
  uuid: string;
  name: string;
  state: string;
  created_at: string;
  updated_at: string;
}

function getGroupKey(char: Character): string {
  return char.base_name || char.name;
}

function buildGroups(chars: Character[]): Record<string, Character[]> {
  const groups: Record<string, Character[]> = {};
  chars.forEach((char) => {
    const key = getGroupKey(char);
    if (!groups[key]) groups[key] = [];
    groups[key].push(char);
  });
  return groups;
}

function isSingleDefaultVersion(group: Character[]): boolean {
  return group.length === 1 && group[0].version_label === "default";
}

export function Step2Characters() {
  const { uuid } = useParams<{ uuid: string }>();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [detectingVersions, setDetectingVersions] = useState(false);
  const [generatingPrompts, setGeneratingPrompts] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasEdits, setHasEdits] = useState(false);
  const [showJson, setShowJson] = useState<Record<string, boolean>>({});
  const [copiedMap, setCopiedMap] = useState<Record<string, boolean>>({});
  const [projectState, setProjectState] = useState<string | null>(null);

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

  useEffect(() => {
    if (!uuid) return;
    const fetchProjectState = async () => {
      try {
        const response = await fetch(`${apiBase}/projects/${uuid}`);
        if (!response.ok) return;
        const data = (await response.json()) as ProjectResponse;
        setProjectState(data.state);
      } catch {
        // silent fail
      }
    };
    fetchProjectState();
  }, [uuid]);

  const hasDownstreamWork = (): boolean => {
    if (!projectState) return false;
    return (
      projectState === "step_3_complete" ||
      projectState === "step_4_complete" ||
      projectState === "step_5_complete"
    );
  };

  const confirmDestructiveSave = (): boolean => {
    if (!hasDownstreamWork()) return true;
    return window.confirm(
      "Saving character changes will clear segment breakdown and prompts — continue?"
    );
  };

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

  const handleDetectVersions = async () => {
    if (!uuid) return;
    if (!confirmDestructiveSave()) return;
    setDetectingVersions(true);
    setError(null);
    try {
      const response = await fetch(
        `${apiBase}/projects/${uuid}/characters/timeline`,
        { method: "POST" }
      );
      if (!response.ok) {
        throw new Error(`Version detection failed: ${response.status}`);
      }
      const data = (await response.json()) as ApiResponse;
      setCharacters(data.characters ?? []);
      setHasEdits(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDetectingVersions(false);
    }
  };

  const handleIdentityAnchorChange = (baseName: string, value: string) => {
    setCharacters((prev) =>
      prev.map((char) =>
        getGroupKey(char) === baseName
          ? { ...char, identity_anchor: value }
          : char
      )
    );
    setHasEdits(true);
  };

  const handleVersionFieldChange = (
    name: string,
    field: "version_label" | "appears_from" | "description",
    value: string
  ) => {
    setCharacters((prev) =>
      prev.map((char) =>
        char.name === name ? { ...char, [field]: value } : char
      )
    );
    setHasEdits(true);
  };

  const handleAddVersion = (baseName: string) => {
    setCharacters((prev) => {
      const groupVersions = prev.filter((c) => getGroupKey(c) === baseName);
      const newIndex = groupVersions.length;
      let newName = `${baseName} (v${newIndex + 1})`;
      let counter = 1;
      while (prev.some((c) => c.name === newName)) {
        newName = `${baseName} (v${newIndex + counter + 1})`;
        counter++;
      }
      const newChar: Character = {
        name: newName,
        base_name: baseName,
        type: groupVersions[0]?.type || "speaking",
        importance: groupVersions[0]?.importance || "minor",
        description: "",
        version_label: "new",
        version_index: newIndex,
        appears_from: "",
        identity_anchor: groupVersions[0]?.identity_anchor || "",
      };
      return [...prev, newChar];
    });
    setHasEdits(true);
  };

  const handleRemoveVersion = (name: string) => {
    setCharacters((prev) => {
      const char = prev.find((c) => c.name === name);
      if (!char) return prev;
      const baseName = getGroupKey(char);
      const group = prev.filter((c) => getGroupKey(c) === baseName);
      if (group.length <= 1) return prev;
      return prev.filter((c) => c.name !== name);
    });
    setHasEdits(true);
  };

  const handleSave = async () => {
    if (!uuid) return;
    if (!confirmDestructiveSave()) return;
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
    if (!confirmDestructiveSave()) return;
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

  const groups = buildGroups(characters);
  const groupKeys = Object.keys(groups);

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
            Fireworks · <span className="text-[#E8E8F0]">Kimi K2.6</span>
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

      {/* Detect Versions Button */}
      {characters.length > 0 && !extracting && (
        <div className="mb-4 flex items-center gap-3">
          <button
            onClick={handleDetectVersions}
            disabled={detectingVersions}
            className={cn(
              "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
              "bg-[#1A1A24] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#1E1E28]",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {detectingVersions ? (
              <AmberBar />
            ) : (
              <Clock size={16} weight="regular" />
            )}
            Detect Versions
          </button>
        </div>
      )}

      {/* Character Groups */}
      {characters.length > 0 && !extracting && (
        <div className="mb-6 flex flex-col gap-6">
          {groupKeys.map((baseName) => {
            const versions = groups[baseName];
            return (
              <div key={baseName} className="border border-[#2A2A35] bg-[#0F0F14]">
                {/* Group Header */}
                <div className="bg-[#1A1A24] p-4 border-b border-[#2A2A35]">
                  <h3 className="font-headline text-lg text-[#E8E8F0]">
                    {baseName}
                  </h3>
                </div>

                {isSingleDefaultVersion(versions) ? (
                  <div className="p-4 flex items-start gap-4">
                    <div className="flex flex-col gap-2 shrink-0">
                      <span className="font-body text-sm text-[#E8E8F0]">
                        {versions[0].name}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border text-[#06B6D4] border-[#06B6D4]/20 bg-[#06B6D4]/10">
                        {versions[0].type}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center px-2 py-0.5 font-body text-xs font-semibold tracking-wide uppercase border",
                          versions[0].importance === "major"
                            ? "text-[#F0A040] border-[#F0A040]/20 bg-[#F0A040]/10"
                            : "text-[#5A5A6A] border-[#5A5A6A]/20 bg-[#5A5A6A]/10"
                        )}
                      >
                        {versions[0].importance}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <textarea
                        value={versions[0].description}
                        onChange={(e) =>
                          handleVersionFieldChange(
                            versions[0].name,
                            "description",
                            e.target.value
                          )
                        }
                        className="w-full bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 resize-y focus:border-[#F0A040] focus:outline-none"
                        rows={4}
                      />
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Identity Anchor */}
                    <div className="bg-[#1A1A24] p-4 border-b border-[#2A2A35]">
                      <div>
                        <label className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] block mb-1">
                          Identity Anchor
                        </label>
                        <textarea
                          value={versions[0]?.identity_anchor || ""}
                          onChange={(e) =>
                            handleIdentityAnchorChange(baseName, e.target.value)
                          }
                          className="w-full bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 resize-none focus:border-[#F0A040] focus:outline-none"
                          rows={2}
                          placeholder="Shared identity anchor for all versions..."
                        />
                      </div>
                    </div>

                    {/* Versions Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-[#1A1A24]">
                          <tr>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Name
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Version
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Appears From
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Description
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Type
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Importance
                            </th>
                            <th className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] px-4 py-3 text-left border-b border-[#2A2A35]">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {versions.map((char) => (
                            <tr
                              key={char.name}
                              className="border-b border-[#2A2A35] last:border-b-0"
                            >
                              <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                                {char.name}
                              </td>
                              <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                                <input
                                  type="text"
                                  value={char.version_label || ""}
                                  onChange={(e) =>
                                    handleVersionFieldChange(
                                      char.name,
                                      "version_label",
                                      e.target.value
                                    )
                                  }
                                  className="w-[120px] bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 focus:border-[#F0A040] focus:outline-none"
                                  placeholder="e.g. default"
                                />
                              </td>
                              <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                                <input
                                  type="text"
                                  value={char.appears_from || ""}
                                  onChange={(e) =>
                                    handleVersionFieldChange(
                                      char.name,
                                      "appears_from",
                                      e.target.value
                                    )
                                  }
                                  className="w-[140px] bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 focus:border-[#F0A040] focus:outline-none"
                                  placeholder="e.g. after the 7-year time skip"
                                />
                              </td>
                              <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 min-w-[200px]">
                                <textarea
                                  value={char.description}
                                  onChange={(e) =>
                                    handleVersionFieldChange(
                                      char.name,
                                      "description",
                                      e.target.value
                                    )
                                  }
                                  className="w-full bg-[#0F0F14] border border-[#2A2A35] text-[#E8E8F0] font-body text-sm p-2 resize-y focus:border-[#F0A040] focus:outline-none"
                                  rows={4}
                                />
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
                                    char.importance === "major"
                                      ? "text-[#F0A040] border-[#F0A040]/20 bg-[#F0A040]/10"
                                      : "text-[#5A5A6A] border-[#5A5A6A]/20 bg-[#5A5A6A]/10"
                                  )}
                                >
                                  {char.importance}
                                </span>
                              </td>
                              <td className="font-body text-sm text-[#E8E8F0] px-4 py-3 whitespace-nowrap">
                                <button
                                  onClick={() => handleRemoveVersion(char.name)}
                                  disabled={versions.length <= 1}
                                  className={cn(
                                    "flex items-center gap-1 px-2 py-1 font-body text-xs font-semibold tracking-wide uppercase",
                                    "bg-[#1A1A24] text-[#EF4444] border border-[#2A2A35] hover:bg-[#1E1E28]",
                                    "disabled:opacity-50 disabled:cursor-not-allowed"
                                  )}
                                  aria-label={`Remove version ${char.name}`}
                                >
                                  <Trash size={14} weight="regular" />
                                  Remove
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                {/* Add Version */}
                <div className="p-3 border-t border-[#2A2A35]">
                  <button
                    onClick={() => handleAddVersion(baseName)}
                    className={cn(
                      "flex items-center gap-2 px-3 py-1.5 font-body text-xs font-semibold tracking-wide uppercase",
                      "bg-[#1A1A24] text-[#E8E8F0] border border-[#2A2A35] hover:bg-[#1E1E28]"
                    )}
                  >
                    <Plus size={14} weight="regular" />
                    Add Version
                  </button>
                </div>
              </div>
            );
          })}

          <div className="flex justify-end gap-3">
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
              disabled={characters.length === 0 || generatingPrompts}
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
        <div className="grid grid-cols-2 gap-4">
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
                      char.importance === "major"
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
                        Turnaround Prompt
                      </span>
                      <button
                        onClick={() =>
                          handleCopy(
                            char.turnaround_prompt ?? "",
                            `turn-${char.name}`
                          )
                        }
                        className="flex items-center gap-1 text-[#8A8A9A] hover:text-[#E8E8F0] font-body text-xs"
                        aria-label={`Copy turnaround prompt for ${char.name}`}
                      >
                        <Copy size={12} weight="regular" />
                        {copiedMap[`turn-${char.name}`] ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p className="font-body text-sm text-[#E8E8F0] bg-[#1A1A24] p-3 border border-[#2A2A35] whitespace-pre-wrap">
                      {char.turnaround_prompt}
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
