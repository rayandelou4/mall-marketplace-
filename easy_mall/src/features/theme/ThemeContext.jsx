import React, { createContext, useContext, useEffect, useState } from "react";
import { LIGHT_TOKENS, DARK_TOKENS } from "../../styles/theme";

const ThemeContext = createContext(null);
const STORAGE_KEY = "mall_theme";

function loadInitialTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark";
  } catch {
    return false;
  }
}

export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(loadInitialTheme);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, isDark ? "dark" : "light");
    } catch {
      // Le thème reste utilisable même si le navigateur bloque le stockage.
    }
  }, [isDark]);

  const value = {
    isDark,
    toggleTheme: () => setIsDark((d) => !d),
    t: isDark ? DARK_TOKENS : LIGHT_TOKENS,
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme() doit être appelé à l'intérieur d'un <ThemeProvider>.");
  return ctx;
}
