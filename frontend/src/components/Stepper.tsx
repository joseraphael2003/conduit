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

const steps = [
  { label: "Script", icon: FileText },
  { label: "Characters", icon: User },
  { label: "Segments", icon: Scissors },
  { label: "Images", icon: Image },
  { label: "Video", icon: FilmStrip },
];

export function Stepper({ currentStep, onStepClick }: StepperProps) {
  return (
    <>
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = stepNumber < currentStep;
        const isPending = stepNumber > currentStep;

        const Icon = step.icon;

        return (
          <div key={step.label} className="flex items-center flex-1 justify-center">
            <button
              onClick={() => onStepClick(stepNumber)}
              className={cn(
                "flex items-center gap-2 px-3 py-2 cursor-pointer select-none",
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
