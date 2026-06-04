import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  FileText,
  User,
  Scissors,
  Image,
  FilmStrip,
} from "@phosphor-icons/react";

interface StepperProps {
  currentStep: number;
  onStepClick: (step: number) => void;
}

interface ProjectState {
  state: string;
}

const steps = [
  { label: "Script", icon: FileText },
  { label: "Characters", icon: User },
  { label: "Segments", icon: Scissors },
  { label: "Images", icon: Image },
  { label: "Video", icon: FilmStrip },
];

const apiBase = "http://localhost:8000/api/v1";

export function Stepper({ currentStep, onStepClick }: StepperProps) {
  const { uuid } = useParams();
  const [projectState, setProjectState] = useState<ProjectState | null>(null);

  useEffect(() => {
    if (!uuid) return;
    const fetchProjectState = async () => {
      try {
        const response = await fetch(`${apiBase}/projects/${uuid}/state`);
        if (!response.ok) return;
        const data = await response.json() as ProjectState;
        setProjectState(data);
      } catch {
        // silent fail on initial load
      }
    };
    fetchProjectState();
  }, [uuid]);

  const isStepComplete = (step: number): boolean => {
    if (!projectState) return false;
    const stateMap: Record<string, number> = {
      created: 0,
      step_1_complete: 1,
      step_2_complete: 2,
      step_3_complete: 3,
      step_4_complete: 4,
      step_5_complete: 5,
    };
    const completedSteps = stateMap[projectState.state] ?? 0;
    return step <= completedSteps;
  };

  return (
    <>
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = isStepComplete(stepNumber);
        const isPending = !isActive && !isCompleted;
        const isClickable = stepNumber <= currentStep || (stepNumber === currentStep + 1 && isStepComplete(currentStep));

        const Icon = step.icon;

        return (
          <div key={step.label} className="flex items-center flex-1 justify-center">
            <button
              onClick={() => onStepClick(stepNumber)}
              disabled={!isClickable}
              className={cn(
                "flex items-center gap-2 px-3 py-2 select-none",
                isClickable ? "cursor-pointer" : "cursor-not-allowed opacity-50",
                isActive && "text-[#F0A040]",
                isCompleted && "text-[#06B6D4]",
                isPending && "text-[#5A5A6A]"
              )}
              aria-label={`Step ${stepNumber}: ${step.label} ${isCompleted ? "— Completed" : isActive ? "— Active" : "— Pending"}`}
              aria-current={isActive ? "step" : undefined}
            >
              <Icon
                weight="regular"
                size={20}
                className={cn(
                  "shrink-0",
                  isActive && "text-[#F0A040]",
                  isCompleted && "text-[#06B6D4]",
                  isPending && "text-[#5A5A6A]"
                )}
              />
              <span className="font-body text-xs font-semibold tracking-wide uppercase">
                {step.label}
              </span>
            </button>
            {index < steps.length - 1 && (
              <span className="ml-4 text-[#2A2A35] select-none">—</span>
            )}
          </div>
        );
      })}
    </>
  );
}
