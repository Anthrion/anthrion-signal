import { flushSync } from 'react-dom'
import { calm } from './delight'
import { getPreferences, setPreference, usePreferences } from './preferences'
import type { Preferences } from './preferences'

export type Theme = Preferences['theme']

export function useTheme(): Theme {
  return usePreferences().theme
}

/**
 * Changes the theme with the new one spreading as a circle from `origin`. Browsers without
 * view transitions, and reduced effects, switch in place.
 */
export function switchTheme(next: Theme, origin: { x: number; y: number }, animate: boolean) {
  const root = document.documentElement
  // Colour transitions would otherwise start from the old theme inside the new snapshot.
  root.dataset.themeSwitching = ''
  const settle = () => delete root.dataset.themeSwitching
  const apply = () => flushSync(() => void setPreference('theme', next))
  if (!animate || typeof document.startViewTransition !== 'function') {
    apply()
    requestAnimationFrame(settle)
    return
  }
  const { x, y } = origin
  // A little past the farthest corner, so no sliver of the old theme is left behind.
  const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) * 1.04
  const transition = document.startViewTransition(apply)
  transition.ready
    .then(() => {
      settle()
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        {
          // Keeps its pace to the end: an easing that slows down leaves the corners waiting.
          duration: 640,
          easing: 'cubic-bezier(0.25, 0.2, 0.7, 0.65)',
          pseudoElement: '::view-transition-new(root)',
        },
      )
    })
    .catch(settle)
}

/** The T shortcut: the other theme, spreading from the header's theme button. */
export function toggleTheme() {
  const bounds = document.querySelector('.theme-toggle')?.getBoundingClientRect()
  const origin = bounds?.width
    ? { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 }
    : { x: innerWidth, y: 0 }
  switchTheme(getPreferences().theme === 'dark' ? 'light' : 'dark', origin, !calm())
}
