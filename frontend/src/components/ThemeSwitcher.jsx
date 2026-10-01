import React, { useEffect, useState } from 'react'
import { IconSun, IconMoon, IconMonitor } from './Icons'

export const ThemeSwitcher = () => {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('vyaparmitra_theme') || 'dark'
  })

  useEffect(() => {
    const applyTheme = (t) => {
      if (t === 'system') {
        const isSystemLight = window.matchMedia('(prefers-color-scheme: light)').matches
        document.documentElement.setAttribute('data-theme', isSystemLight ? 'light' : 'dark')
      } else {
        document.documentElement.setAttribute('data-theme', t)
      }
    }

    applyTheme(theme)
    localStorage.setItem('vyaparmitra_theme', theme)

    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
      const handleChange = () => applyTheme('system')
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    }
  }, [theme])

  return (
    <div className="theme-switcher-segmented" role="group" aria-label="Theme mode switcher">
      <button
        type="button"
        className={`theme-segment-btn ${theme === 'light' ? 'active' : ''}`}
        onClick={() => setTheme('light')}
        title="Light Mode (Crisp Neutral)"
        aria-label="Light mode"
      >
        <IconSun size={14} />
      </button>
      <button
        type="button"
        className={`theme-segment-btn ${theme === 'dark' ? 'active' : ''}`}
        onClick={() => setTheme('dark')}
        title="Dark Mode (Graphite Fintech)"
        aria-label="Dark mode"
      >
        <IconMoon size={14} />
      </button>
      <button
        type="button"
        className={`theme-segment-btn ${theme === 'system' ? 'active' : ''}`}
        onClick={() => setTheme('system')}
        title="System Preference"
        aria-label="System theme"
      >
        <IconMonitor size={14} />
      </button>
    </div>
  )
}
