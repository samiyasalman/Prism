"use client";

interface Props {
  score: number;
  level: string;
}

export default function TrustScoreGauge({ score, level }: Props) {
  const circumference = 2 * Math.PI * 60;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 80
      ? "text-emerald-500"
      : score >= 60
      ? "text-blue-500"
      : score >= 40
      ? "text-amber-500"
      : "text-slate-400";

  const strokeColor =
    score >= 80
      ? "#10b981"
      : score >= 60
      ? "#3b82f6"
      : score >= 40
      ? "#f59e0b"
      : "#94a3b8";

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-40 h-40">
        <svg className="w-40 h-40 -rotate-90" viewBox="0 0 128 128">
          <circle
            cx="64"
            cy="64"
            r="60"
            fill="none"
            stroke="#e2e8f0"
            strokeWidth="8"
          />
          <circle
            cx="64"
            cy="64"
            r="60"
            fill="none"
            stroke={strokeColor}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${color}`}>{score}</span>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
      </div>
      <span className={`mt-2 text-lg font-semibold ${color}`}>{level}</span>
    </div>
  );
}
