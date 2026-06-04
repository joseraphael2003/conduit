import { cn } from "@/lib/utils";

interface SkeletonTableProps {
  columns: number;
  rows?: number;
  className?: string;
}

export function SkeletonTable({
  columns,
  rows = 5,
  className,
}: SkeletonTableProps) {
  return (
    <div
      data-testid="skeleton"
      aria-busy="true"
      role="status"
      aria-label="Loading"
      className={cn("overflow-x-auto border border-[#2A2A35]", className)}
    >
      <table className="w-full">
        <thead className="bg-[#1A1A24]">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th
                key={`head-${i}`}
                className="px-4 py-3 border-b border-[#2A2A35]"
              >
                <div className="h-4 bg-[#1E1E28] w-20 animate-shimmer" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr
              key={`row-${rowIndex}`}
              className="border-b border-[#2A2A35] last:border-b-0"
            >
              {Array.from({ length: columns }).map((_, colIndex) => (
                <td key={`cell-${rowIndex}-${colIndex}`} className="px-4 py-3">
                  <div className="h-4 bg-[#1E1E28] w-full animate-shimmer" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
