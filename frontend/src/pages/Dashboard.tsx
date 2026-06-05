import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Trash, ArrowRight } from "@phosphor-icons/react";
import { apiBase } from "@/config";

interface Project {
  uuid: string;
  name: string;
  state: string;
  created_at: string;
  updated_at: string;
}

function statusColor(state: string): string {
  if (state === "step_5_complete") {
    return "bg-[#06B6D4]/10 text-[#06B6D4] border-[#06B6D4]/20";
  }
  if (state === "created") {
    return "bg-[#5A5A6A]/10 text-[#5A5A6A] border-[#5A5A6A]/20";
  }
  return "bg-[#F0A040]/10 text-[#F0A040] border-[#F0A040]/20";
}

function statusLabel(state: string): string {
  if (state === "step_5_complete") return "completed";
  if (state === "created") return "pending";
  return "active";
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const response = await fetch(apiBase + "/projects");
        if (!response.ok) {
          throw new Error(`Failed to fetch projects: ${response.status}`);
        }
        const data = (await response.json()) as { projects: Project[] };
        setProjects(data.projects);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const handleCreate = async () => {
    const name = window.prompt("Enter project name:");
    if (!name || name.trim() === "") return;
    try {
      const response = await fetch(apiBase + "/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!response.ok) {
        throw new Error(`Failed to create project: ${response.status}`);
      }
      const newProject = (await response.json()) as Project;
      setProjects((prev) => [newProject, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleDelete = async (uuid: string) => {
    if (!window.confirm("Are you sure you want to delete this project?")) return;
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Failed to delete project: ${response.status}`);
      }
      setProjects((prev) => prev.filter((p) => p.uuid !== uuid));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleOpen = (uuid: string) => {
    navigate(`/project/${uuid}`);
  };

  return (
    <div className="min-h-screen bg-[#0F0F14] text-[#E8E8F0] font-body">
      {/* Header */}
      <header className="h-[64px] flex items-center justify-between px-6 border-b border-[#2A2A35] bg-[#0F0F14]">
        <h1 className="font-headline text-2xl text-[#E8E8F0]">Conduit</h1>
        <button
          onClick={handleCreate}
          className={cn(
            "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]"
          )}
        >
          Create Project
          <ArrowRight size={16} weight="regular" />
        </button>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-[960px] mx-auto">
        {loading && (
          <div className="flex items-center justify-center h-[400px]">
            <span className="font-body text-[#8A8A9A] text-lg">Loading projects...</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex items-center justify-center h-[400px]">
            <span className="font-body text-[#EF4444] text-lg">Error: {error}</span>
          </div>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className="flex flex-col items-center justify-center h-[calc(100vh-128px)]">
            {/* Geometric illustration */}
            <div className="relative w-[120px] h-[120px] mb-6">
              <div className="absolute top-0 left-0 w-[80px] h-[60px] bg-[#1E1E28] border border-[#5A5A6A]" />
              <div className="absolute top-[20px] left-[20px] w-[80px] h-[60px] bg-[#5A5A6A] border border-[#1E1E28]" />
              <div className="absolute top-[40px] left-[40px] w-[80px] h-[60px] bg-[#1E1E28] border border-[#5A5A6A]" />
            </div>
            <p className="font-body text-lg text-[#8A8A9A] text-center max-w-[360px]">
              No projects yet. Create your first project to get started.
            </p>
          </div>
        )}

        {!loading && !error && projects.length > 0 && (
          <div className="flex flex-col gap-4">
            {projects.map((project) => (
              <div
                key={project.uuid}
                className="bg-[#0F0F14] border border-[#2A2A35] p-4 flex items-center justify-between"
              >
                <div className="flex flex-col gap-1">
                  <h2 className="font-headline text-xl text-[#E8E8F0]">
                    {project.name}
                  </h2>
                  <span className="font-mono text-xs text-[#8A8A9A]">
                    {formatDate(project.created_at)}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 mt-1 font-body text-xs font-semibold tracking-wide uppercase border",
                      statusColor(project.state)
                    )}
                  >
                    {statusLabel(project.state)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                    onClick={() => handleOpen(project.uuid)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-2 font-body text-sm font-medium",
                      "bg-transparent text-[#06B6D4] hover:bg-[#1A1A24]"
                    )}
                  >
                    Open
                    <ArrowRight size={14} weight="regular" />
                  </button>
                  <button
                    onClick={() => handleDelete(project.uuid)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-2 font-body text-sm font-medium",
                      "bg-transparent text-[#EF4444] hover:bg-[#1A1A24]"
                    )}
                  >
                    <Trash size={14} weight="regular" />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
