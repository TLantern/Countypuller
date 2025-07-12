"use client";
import { useTheme } from "@/context/ThemeContext";

interface ThemeToggleProps {
  isHidden?: boolean;
  inHeader?: boolean;
}

export default function ThemeToggle({ isHidden = false, inHeader = false }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  
  if (isHidden) return null;
  
  const baseStyles = {
    background: '#1a1a1a',
    border: '2px solid #333',
    borderRadius: '50px',
    cursor: 'pointer',
    fontSize: 20,
    zIndex: 1000,
    width: '80px',
    height: '40px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: theme === 'dark' ? 'flex-end' : 'flex-start',
    padding: '4px',
    transition: 'all 0.3s ease',
    boxShadow: '0 0 20px rgba(255, 255, 255, 0.4), 0 0 40px rgba(255, 255, 255, 0.2), 0 4px 8px rgba(0, 0, 0, 0.3)',
  };

  const positionStyles = inHeader 
    ? { position: 'relative' as const }
    : { position: 'fixed' as const, top: 24, right: 24 };
  
  return (
    <button
      onClick={toggleTheme}
      style={{
        ...baseStyles,
        ...positionStyles,
      }}
      aria-label="Toggle theme"
      title="Toggle light/dark mode"
    >
      <div
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          background: theme === 'dark' ? '#4a5568' : '#ffd700',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '16px',
          transition: 'all 0.3s ease',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.2)',
        }}
      >
        {theme === 'dark' ? '🌙' : '☀️'}
      </div>
    </button>
  );
}