"use client";
import { useTheme } from "@/context/ThemeContext";

interface ThemeToggleProps {
  isHidden?: boolean;
}

export default function ThemeToggle({ isHidden = false }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  
  if (isHidden) return null;
  
  return (
    <button
      onClick={toggleTheme}
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        fontSize: 28,
        position: 'fixed',
        top: 10,
        right: 24,
        zIndex: 1000,
      }}
      aria-label="Toggle theme"
      title="Toggle light/dark mode"
    >
      {theme === 'dark' ? '🌙' : '☀️'}
    </button>
  );
}