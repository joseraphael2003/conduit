import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { cn } from "@/lib/utils";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { Stepper } from "./Stepper";
import { ArrowLeft, ArrowRight, Warning, X } from "@phosphor-icons/react";
import { Step1Script } from "@/pages/Step1Script";
import { Step2Characters } from "@/pages/Step2Characters";
import { Step3Segments } from "@/pages/Step3Segments";
import { Step4Images } from "@/pages/Step4Images";
import { Step5Video } from "@/pages/Step5Video";
import { apiBase } from "@/config";
import { type ProjectState, isStepComplete } from "@/lib/projectState";

interface ProjectResponse {
  uuid: string;
  name: string;
  state: string;
  created_at: string;
  updated_at: string;
}

interface WizardShellProps {
  children?: React.ReactNode;
}

function fallbackRender({ error, resetErrorBoundary }: FallbackProps) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div
      className="flex flex-col items-center justify-center h-full gap-4 bg-[#0F0F14] p-4"
      data-testid="error-boundary"
    >
      <h2 className="font-headline text-2xl text-[#F0A040]">Something went wrong</h2>
      <p className="font-body text-sm text-[#E8E8F0] max-w-[640px] text-center">
        {message}
      </p>
      <button
        onClick={resetErrorBoundary}
        className={cn(
          "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
          "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]"
        )}
      >
        Try again
      </button>
    </div>
  );
}

export function WizardShell({ children }: WizardShellProps) {
  const { uuid, stepNumber } = useParams();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(() => {
    const num = parseInt(stepNumber || "1", 10);
    return isNaN(num) ? 1 : Math.max(1, Math.min(5, num));
  });
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [step1Data, setStep1Data] = useState({
    hasTranscript: false,
    hasScript: false,
    fidelity: null as number | null,
  });
  const [isWarningModalOpen, setIsWarningModalOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useFocusTrap(isWarningModalOpen, () => setIsWarningModalOpen(false), triggerRef);

  useEffect(() => {
    const num = parseInt(stepNumber || "1", 10);
    if (!isNaN(num)) {
      setCurrentStep(Math.max(1, Math.min(5, num)));
    }
  }, [stepNumber]);

  const refreshProjectState = useCallback(async (signal?: AbortSignal) => {
    if (!uuid) return;
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/state`, { signal });
      if (!response.ok) return;
      const data = (await response.json()) as ProjectState;
      setProjectState(data);
    } catch {
      // silent fail on initial load
    }
  }, [uuid]);

  useEffect(() => {
    if (!uuid) return;
    const controller = new AbortController();
    refreshProjectState(controller.signal);
    return () => controller.abort();
  }, [uuid, currentStep, refreshProjectState]);

  useEffect(() => {
    if (!uuid) return;
    const controller = new AbortController();
    const fetchProjectName = async (signal: AbortSignal) => {
      try {
        const response = await fetch(`${apiBase}/projects/${uuid}`, { signal });
        if (!response.ok) return;
        const data = (await response.json()) as ProjectResponse;
        setProjectName(data.name || "");
      } catch {
        // silent fail on initial load
      }
    };
    fetchProjectName(controller.signal);
    return () => controller.abort();
  }, [uuid]);

  const handleStep1Ready = useCallback((data: { hasTranscript: boolean; hasScript: boolean; fidelity: number | null }) => {
    setStep1Data(data);
  }, []);

  const handleBack = () => {
    if (currentStep > 1) {
      const nextStep = currentStep - 1;
      setCurrentStep(nextStep);
      navigate(`/project/${uuid}/step/${nextStep}`);
    }
  };

  const goToStep = (nextStep: number) => {
    setCurrentStep(nextStep);
    navigate(`/project/${uuid}/step/${nextStep}`);
  };

  const handleNext = () => {
    if (currentStep < 5) {
      const nextStep = currentStep + 1;
      if (
        currentStep === 1 &&
        step1Data.hasScript &&
        step1Data.fidelity !== null &&
        step1Data.fidelity < 95
      ) {
        triggerRef.current = document.activeElement as HTMLButtonElement;
        setIsWarningModalOpen(true);
        return;
      }
      goToStep(nextStep);
    }
  };

  const stepLabels = ["Script", "Characters", "Segments", "Images", "Video"];
  const stepLabel = stepLabels[currentStep - 1] ?? "";

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <Step1Script onStep1Ready={handleStep1Ready} />;
      case 2:
        return <Step2Characters onStateChange={refreshProjectState} />;
      case 3:
        return <Step3Segments onStateChange={refreshProjectState} />;
      case 4:
        return <Step4Images onStateChange={refreshProjectState} />;
      case 5:
        return <Step5Video />;
      default:
        return children;
    }
  };

  const isCurrentStepComplete = isStepComplete(projectState, currentStep);
  const canGoNext = currentStep === 1
    ? step1Data.hasTranscript && currentStep < 5
    : isCurrentStepComplete && currentStep < 5;

  return (
    <div className="wizard-shell flex flex-col h-screen">
      {/* Title Bar */}
      <header className="title-bar h-[48px] flex items-center justify-between px-4 bg-[#0F0F14] border-b border-[#2A2A35] shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="font-headline text-2xl text-[#E8E8F0]">Conduit</h1>
          <span className="font-body text-sm text-[#8A8A9A]">{projectName || "Untitled Project"}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-body text-xs font-semibold tracking-wide uppercase text-[#8A8A9A] bg-[#1E1E28] px-2 py-1">
            Step {currentStep} of 5 — {stepLabel}
          </span>
        </div>
      </header>

      {/* Stepper Bar */}
      <nav className="stepper h-[56px] bg-[#0A0A0F] border-b border-[#2A2A35] shrink-0 flex items-center justify-between px-8" aria-label="Wizard steps">
        <Stepper currentStep={currentStep} projectState={projectState} onStepClick={(step) => goToStep(step)} />
      </nav>

      {/* Main Content Area */}
      <main className="content flex-1 overflow-y-auto bg-[#0F0F14] p-4">
        <ErrorBoundary fallbackRender={fallbackRender}>
          {renderStepContent()}
        </ErrorBoundary>
      </main>

      {/* Action Bar */}
      <footer className="action-bar h-[64px] flex items-center justify-between px-4 bg-[#1A1A24] border-t border-[#2A2A35] shrink-0">
        <button
          onClick={handleBack}
          disabled={currentStep === 1}
          className={cn(
            "flex items-center gap-2 px-6 py-2.5 font-body text-sm font-semibold tracking-wide uppercase",
            "bg-transparent text-[#8A8A9A] hover:bg-[#1A1A24] hover:text-[#E8E8F0]",
            "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[#8A8A9A]"
          )}
        >
          <ArrowLeft size={16} weight="regular" />
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={!canGoNext}
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

      {/* Low Fidelity Warning Modal */}
      {isWarningModalOpen && (
        <div
          ref={modalRef}
          className="fixed inset-0 bg-[#0F0F14]/80 flex items-center justify-center z-50 p-4"
          onClick={() => setIsWarningModalOpen(false)}
          data-testid="warning-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="warning-modal-title"
        >
          <div
            className="bg-[#1A1A24] border border-[#2A2A35] w-full max-w-[520px] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#2A2A35]">
              <h2
                id="warning-modal-title"
                className="font-headline text-xl text-[#E8E8F0]"
              >
                Low Fidelity Warning
              </h2>
              <button
                onClick={() => setIsWarningModalOpen(false)}
                className="flex items-center justify-center w-8 h-8 bg-transparent text-[#8A8A9A] hover:text-[#E8E8F0] hover:bg-[#1A1A24]"
                aria-label="Close warning modal"
              >
                <X size={18} weight="regular" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex flex-col gap-4 p-4">
              <div className="flex items-start gap-3">
                <Warning size={20} weight="regular" className="text-[#F0A040] mt-0.5 shrink-0" />
                <p className="font-body text-sm text-[#E8E8F0]">
                  Your transcript fidelity is {step1Data.fidelity}%. This means there are significant differences between your voiceover and the original script. You can review the changes or proceed anyway.
                </p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-[#2A2A35]">
              <button
                onClick={() => setIsWarningModalOpen(false)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 font-body text-sm font-semibold tracking-wide uppercase",
                  "bg-transparent text-[#8A8A9A] hover:bg-[#1A1A24] hover:text-[#E8E8F0]"
                )}
                data-testid="continue-reviewing"
              >
                Continue Reviewing
              </button>
              <button
                onClick={() => {
                  setIsWarningModalOpen(false);
                  goToStep(2);
                }}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 font-body text-sm font-semibold tracking-wide uppercase",
                  "bg-[#F0A040] text-[#0F0F14] hover:bg-[#F5B860]"
                )}
                data-testid="review-anyway"
              >
                Review Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
