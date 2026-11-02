export const cx = (...parts) => parts.filter(Boolean).join(" ");

export const LIGHT_TOKENS = {
  pageBg: "bg-zinc-50",
  headerBg: "bg-white/85",
  textPrimary: "text-zinc-900",
  textMuted: "text-zinc-500",
  cardBg: "bg-white",
  cardBorder: "border-zinc-200",
  surfaceAlt: "bg-zinc-100/70",
  border: "border-zinc-200",
  accentText: "text-indigo-600",
  inputBg: "bg-zinc-50",
};

export const DARK_TOKENS = {
  pageBg: "bg-zinc-950",
  headerBg: "bg-zinc-950/80",
  textPrimary: "text-zinc-50",
  textMuted: "text-zinc-400",
  cardBg: "bg-zinc-900",
  cardBorder: "border-zinc-800",
  surfaceAlt: "bg-zinc-900/60",
  border: "border-zinc-800",
  accentText: "text-indigo-400",
  inputBg: "bg-zinc-900",
};
