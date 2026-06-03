import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Stepper } from "./Stepper";
import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { Step2Characters } from "@/pages/Step2Characters";
import { Step3Segments } from "@/pages/Step3Segments";
import { Step4Images } from "@/pages/Step4Images";

interface WizardShellProps {
  children?: React.ReactNode;
}

export function WizardShell({ children }: WizardShellProps) {
  const { stepNumber } = useParams();
  const [currentStep, setCurrentStep] = useState(() => {
    const num = parseInt(stepNumber || "1", 10);
    return isNaN(num) ? 1 : Math.max(1, Math.min(5, num));
  });

  useEffect(() => {
    const num = parseInt(stepNumber || "1", 10);
    if (!isNaN(num)) {
      setCurrentStep(Math.max(1, Math.min(5, num)));
    }
  }, [stepNumber]);

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((s) => s - 1);
    }
  };

  const handleNext = () => {
    if (currentStep < 5) {
      setCurrentStep((s) => s + 1);
    }
  };

  const stepLabels = ["Script", "Characters", "Segments", "Images", "Video"];
  const stepLabel = stepLabels[currentStep - 1] ?? "";

  const renderStepContent = () => {
    switch (currentStep) {
      case 2:
        return <Step2Characters />;
      case 3:
        return <Step3Segments />;
      case 4:
        return <Step4Images />;
      default:
        return children;
    }
  };

  return (
    <div className="wizard-shell flex flex-col h-screen">
      {/* Title Bar */}
      <header className="title-bar h-[48px] flex items-center justify-between px-4 bg-[#0F0F14] border-b border-[#2A2A35] shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="font-headline text-2xl text-[#E8E8F0]">Conduit</h1>
          <span className="font-body text-sm text-[#8A8A9A]">Untitled Project</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] bg-[#1E1E28] px-2 py-1">
            Step {currentStep} of 5 — {stepLabel}
          </span>
        </div>
      </header>

      {/* Stepper Bar */}
      <nav className="stepper h-[56px] bg-[#0A0A0F] border-b border-[#2A2A35] shrink-0 flex items-center justify-between px-8" aria-label="Wizard steps">
        <Stepper currentStep={currentStep} onStepClick={setCurrentStep} />
      </nav>

      {/* Main Content Area */}
      <main className="content flex-1 overflow-y-auto bg-[#0F0F14] p-4">
        {renderStepContent()}
      </main>

      {/* Action Bar */}
      <footer className="action-bar h-[64px] flex items-center justify-between px-4 bg-[#1A1A24] border-t border-[#2A2A35] shrink-0">
        <button
          onClick={handleBack}
          disabled={currentStep === 1}
          className={cn(
            "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-transparent text-[#8A8A9A] hover:bg-[#1E1E28] hover:text-[#E8E8F0]",
            "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[#8A8A9A]"
          )}
        >
          <ArrowLeft size={16} weight="regular" />
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={currentStep === 5}
          className={cn(
            "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]",
            "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-[#F0A040]"
          )}
        >
          Next
          <ArrowRight size={16} weight="regular" />
        </button>
      </footer>
    </div>
  );
}
