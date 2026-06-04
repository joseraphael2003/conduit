export function AmberBar() {
  return (
    <div className="w-[120px] h-[2px] bg-[#1A1A24] overflow-hidden relative">
      <div className="h-full bg-[#F0A040] amber-bar-fill" />
      <style>{`
        @keyframes amberBarSlide {
          0% {
            transform: translateX(-60px);
          }
          100% {
            transform: translateX(120px);
          }
        }
        .amber-bar-fill {
          width: 60px;
          animation: amberBarSlide 300ms ease-out infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .amber-bar-fill {
            animation: none;
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
