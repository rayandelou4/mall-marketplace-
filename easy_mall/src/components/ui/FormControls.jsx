import React, { useId, useState } from "react";
import { Eye, EyeOff, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { cx } from "../../styles/theme";

export function TextField({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  required,
  hint,
  t,
  maxLength,
  min,
  max,
  step,
  inputMode,
  autoComplete,
}) {
  return (
    <label className="block">
      <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        maxLength={maxLength}
        min={min}
        max={max}
        step={step}
        inputMode={inputMode}
        autoComplete={autoComplete}
        className={cx(
          "w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition focus:border-indigo-500",
          t.inputBg,
          t.border,
          t.textPrimary
        )}
      />
      {hint && <span className={cx("mt-1 block text-xs", t.textMuted)}>{hint}</span>}
    </label>
  );
}

export function AreaField({ label, value, onChange, areas, placeholder, maxLength, t }) {
  const listId = useId();
  return (
    <label className="block">
      <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        list={listId}
        className={cx(
          "w-full rounded-xl border px-4 py-2.5 text-sm outline-none transition focus:border-indigo-500",
          t.inputBg,
          t.border,
          t.textPrimary
        )}
      />
      <datalist id={listId}>
        {areas.map((area) => <option key={area.id} value={area.name} />)}
      </datalist>
    </label>
  );
}

export function PasswordField({ label, value, onChange, t, autoComplete }) {
  const [show, setShow] = useState(false);
  return (
    <label className="block">
      <span className={cx("mb-1 block text-sm font-medium", t.textPrimary)}>{label}</span>
      <div className={cx("flex items-center rounded-xl border px-4 focus-within:border-indigo-500", t.inputBg, t.border)}>
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          autoComplete={autoComplete}
          className={cx("w-full bg-transparent py-2.5 text-sm outline-none", t.textPrimary)}
        />
        <button type="button" onClick={() => setShow(!show)} className={t.textMuted} aria-label="Afficher le mot de passe">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </label>
  );
}

export function Button({ children, variant = "primary", loading, className, ...props }) {
  const variants = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    ghost: "border border-current text-indigo-600 hover:bg-indigo-50",
  };
  return (
    <button
      className={cx(
        "flex w-full items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition disabled:opacity-60",
        variants[variant],
        className
      )}
      disabled={loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Alert({ type = "error", children }) {
  const isError = type === "error";
  const Icon = isError ? AlertCircle : CheckCircle2;
  return (
    <div
      className={cx(
        "mb-4 flex items-start gap-2 rounded-xl border px-3 py-2 text-sm",
        isError ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
