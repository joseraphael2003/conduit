import { cn } from "@/lib/utils";
import {
  FileText,
  User,
  Scissors,
  Image,
  FilmStrip,
} from "@phosphor-icons/react";
import { type ProjectState, isStepComplete } from "@/lib/projectState";

interface StepperProps {
  currentStep: number;
  projectState: ProjectState | null;
  onStepClick: (step: number) => void;
}

const steps = [
  { label: "Script", icon: FileText },
  { label: "Characters", icon: User },
  { label: "Segments", icon: Scissors },
  { label: "Images", icon: Image },
  { label: "Video", icon: FilmStrip },
];

export function Stepper({ currentStep, projectState, onStepClick }: StepperProps) {
  return (
    <>
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = isStepComplete(projectState, stepNumber);
        const isPending = !isActive && !isCompleted;
        const isClickable = stepNumber <= currentStep || (stepNumber === currentStep + 1 && isStepComplete(projectState, currentStep));

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
