/**
 * Accessibility safety net, applied to the whole app as screens render.
 *
 * Most forms in this app are written as <label class="label">Name</label><input ...> with the two
 * next to each other but not linked, so screen readers announce "edit text" with no name. Rather than
 * touch every form, this links each such label to the control that follows it, names icon-only
 * buttons from their title, and marks decorative icons as hidden. New code should still use
 * htmlFor/id or aria-label directly; this only fills the gaps.
 */
let counter = 0
const CONTROL = 'input:not([type=hidden]), select, textarea'

function enhance(root) {
  root.querySelectorAll('label:not([for])').forEach((label) => {
    if (label.querySelector(CONTROL)) return // already wrapped around its control
    let control = null
    const next = label.nextElementSibling
    if (next && next.matches?.(CONTROL)) control = next
    else if (next) control = next.querySelector?.(CONTROL)
    if (!control) control = label.parentElement?.querySelector(CONTROL)
    if (!control) return
    if (!control.id) control.id = `field-${++counter}`
    label.setAttribute('for', control.id)
  })

  root.querySelectorAll('button:not([aria-label]), a:not([aria-label])').forEach((el) => {
    if (el.textContent.trim()) return
    const name = el.getAttribute('title') || el.getAttribute('data-label')
    if (name) el.setAttribute('aria-label', name)
  })

  root.querySelectorAll('input:not([aria-label]):not([id]), select:not([aria-label]):not([id]), textarea:not([aria-label]):not([id])').forEach((el) => {
    const hint = el.getAttribute('placeholder')
    if (hint && el.type !== 'hidden') el.setAttribute('aria-label', hint)
  })

  root.querySelectorAll('svg.lucide:not([aria-hidden])').forEach((svg) => svg.setAttribute('aria-hidden', 'true'))
  root.querySelectorAll('img:not([alt])').forEach((img) => img.setAttribute('alt', ''))
}

export function initA11y() {
  if (typeof document === 'undefined') return
  let scheduled = false
  const run = () => {
    scheduled = false
    enhance(document.body)
  }
  new MutationObserver(() => {
    if (!scheduled) {
      scheduled = true
      requestAnimationFrame(run)
    }
  }).observe(document.body, { childList: true, subtree: true })
  run()
}
