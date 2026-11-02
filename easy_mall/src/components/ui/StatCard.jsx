import React from "react";
import { cx } from "../../styles/theme";

export function StatCard({ icon: Icon, label, value, t }) {
  return (
    <div className={cx("rounded-2xl border p-4", t.cardBorder, t.cardBg)}>
      <Icon className="h-4 w-4 text-indigo-600" />
      <p className={cx("mt-2 text-xl font-semibold", t.textPrimary)}>{value}</p>
      <p className={cx("text-xs", t.textMuted)}>{label}</p>
    </div>
  );
}
