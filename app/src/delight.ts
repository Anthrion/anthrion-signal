/** True when the system or Signal's Effects preference asks for less motion. */
export function calm() {
  return (
    matchMedia('(prefers-reduced-motion: reduce)').matches ||
    document.documentElement.dataset.effects === 'reduced'
  )
}

/** A short spring on the control that was just used, such as saving a record. */
export function pop(element: Element | null) {
  if (!element || calm()) return
  element.animate(
    [
      { transform: 'scale(1)' },
      { transform: 'scale(1.3)', offset: 0.32 },
      { transform: 'scale(1)' },
    ],
    { duration: 480, easing: 'cubic-bezier(0.3, 1.5, 0.5, 1)' },
  )
}

/** Light spreading from where a glass surface was pressed. */
export function ripple(surface: Element | null, x: number, y: number) {
  if (!surface || calm()) return
  const bounds = surface.getBoundingClientRect()
  const size = Math.hypot(bounds.width, bounds.height) * 2
  const light = document.createElement('span')
  light.className = 'glass-ripple'
  light.style.left = `${x - bounds.left - size / 2}px`
  light.style.top = `${y - bounds.top - size / 2}px`
  light.style.width = light.style.height = `${size}px`
  surface.append(light)
  light
    .animate(
      [
        { transform: 'scale(0.02)', opacity: 0.9 },
        { transform: 'scale(1)', opacity: 0 },
      ],
      { duration: 900, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)' },
    )
    .finished.then(
      () => light.remove(),
      () => light.remove(),
    )
}
