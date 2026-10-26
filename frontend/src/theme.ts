import { useSyncExternalStore } from 'react'

/**
 * Light/dark theme state for the app.
 *
 * - The active theme is written to <html data-theme="light|dark">, which the
 *   CSS custom properties in styles.css key off (`html[data-theme='dark']`).
 * - The user's choice is persisted in localStorage; on first visit the
 *   OS preference (prefers-color-scheme) decides.
 * - Components subscribe through useTheme(); initTheme() runs once from
 *   main.tsx before render so there is no flash of the wrong theme.
 */

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'netspace-theme'

function systemTheme(): Theme {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

function readStored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null // storage blocked (private mode etc.)
  }
}

/** Current theme from the DOM (single source of truth). */
export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function apply(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}

/** Persist + apply a theme choice. */
export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* storage blocked — still apply for this session */
  }
  apply(theme)
  listeners.forEach((listener) => listener())
}

/** Toggle between light and dark; returns the new theme. */
export function toggleTheme(): Theme {
  const next = getTheme() === 'dark' ? 'light' : 'dark'
  setTheme(next)
  return next
}

/** Called once before first render (main.tsx). Returns the resolved theme. */
export function initTheme(): Theme {
  const theme = readStored() ?? systemTheme()
  apply(theme)
  return theme
}

/* --- subscription for useSyncExternalStore ------------------------- */

const listeners = new Set<() => void>()

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** React hook: re-renders when the theme changes. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getTheme, () => 'light' as Theme)
}
