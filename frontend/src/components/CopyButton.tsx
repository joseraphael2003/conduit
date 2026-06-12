import { useState } from "react";
import { Copy, Check } from "@phosphor-icons/react";

interface CopyButtonProps {
  text: string;
  ariaLabel: string;
  label?: string;
  size?: number;
  className?: string;
  disabled?: boolean;
  title?: string;
}

export function CopyButton({
  text,
  ariaLabel,
  label,
  size = 12,
  className = "",
  disabled = false,
  title,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleClick = async () => {
    if (disabled) return;

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleClick}
      className={`flex items-center gap-1 text-[#8A8A9A] hover:text-[#E8E8F0] font-body text-xs transition-opacity ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${className}`}
      aria-label={ariaLabel}
      aria-disabled={disabled}
      title={title}
    >
      {copied ? (
        <Check size={size} weight="regular" />
      ) : (
        <Copy size={size} weight="regular" />
      )}
      {label && (copied ? "Copied" : label)}
    </button>
  );
}
