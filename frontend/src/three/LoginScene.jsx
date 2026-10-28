import { useEffect, useRef, useState } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'

/**
 * A real CSS-3D scene, perspective + rotateX/rotateY/translateZ, not a
 * flat drop-shadow illusion. Deliberately not WebGL/three.js: this school's
 * own brief calls out low-end Android devices and patchy connectivity as
 * first-class constraints, and a GPU canvas scene is a poor fit for that
 * hardware. Compositor-accelerated CSS transforms give genuine depth at a
 * fraction of the cost, and degrade gracefully (prefers-reduced-motion
 * collapses it to a static, still-dimensional stack).
 *
 * The subject: a stack of Sierra Leonean school exercise books, each with
 * a visible spine, a ruled-paper edge, and a subject badge, tilted in
 * real 3D space and responding to pointer movement like objects sitting
 * on a desk, not icons floating in a gradient void.
 */

const BOOKS = [
  { color: '#1EB53A', label: 'MATHEMATICS', z: 40, baseRotate: -10, offsetX: -70, offsetY: 20 },
  { color: '#1C7ED6', label: 'ENGLISH', z: 20, baseRotate: 6, offsetX: 55, offsetY: -45 },
  { color: '#F2A93B', label: 'INTEGRATED SCIENCE', z: 0, baseRotate: -4, offsetX: 10, offsetY: 70 },
  { color: '#4B5567', label: 'SOCIAL STUDIES', z: -20, baseRotate: 12, offsetX: -30, offsetY: -80 },
]

function Copybook({ book, index, tiltX, tiltY }) {
  const rotate = useTransform([tiltX, tiltY], ([tx, ty]) => book.baseRotate + tx * 0.4 + ty * 0.15)
  const liftY = useTransform(tiltY, (ty) => -ty * 0.3)

  return (
    <motion.div
      className="absolute left-1/2 top-1/2"
      style={{
        x: book.offsetX, y: book.offsetY, z: book.z,
        rotate, translateY: liftY,
        transformStyle: 'preserve-3d',
      }}
      initial={{ opacity: 0, scale: 0.85, z: book.z - 60 }}
      animate={{ opacity: 1, scale: 1, z: book.z }}
      transition={{ duration: 0.7, delay: 0.15 + index * 0.1, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Idle breathing float, independent of pointer tilt */}
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 5 + index, repeat: Infinity, ease: 'easeInOut', delay: index * 0.4 }}
        style={{ transformStyle: 'preserve-3d' }}
      >
        <div className="relative w-36 h-48" style={{ transformStyle: 'preserve-3d' }}>
          {/* Spine, a separate 3D plane rotated to sit at the book's left edge, giving real depth */}
          <div
            className="absolute left-0 top-0 bottom-0 w-4 rounded-l-sm"
            style={{
              background: `linear-gradient(180deg, ${book.color}, ${book.color}99)`,
              transform: 'rotateY(-35deg) translateZ(-6px)',
              transformOrigin: 'left center',
              boxShadow: 'inset -2px 0 4px rgba(0,0,0,0.25)',
            }}
          />
          {/* Page edges peeking out the right side, in their own depth plane */}
          <div
            className="absolute right-0 top-1.5 bottom-1.5 w-2.5 bg-paper/95 rounded-r-[2px]"
            style={{ transform: 'translateZ(2px)' }}
          >
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-px bg-ink/15 mx-0.5" style={{ marginTop: i === 0 ? 4 : 5 }} />
            ))}
          </div>
          {/* Front cover */}
          <div
            className="absolute inset-0 rounded-[3px] flex flex-col items-center justify-center px-4"
            style={{
              background: `linear-gradient(155deg, ${book.color} 0%, ${book.color}cc 100%)`,
              boxShadow: '0 20px 40px -12px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)',
              transform: 'translateZ(0px)',
            }}
          >
            <div className="w-full h-full border border-white/15 rounded-[2px] flex flex-col items-center justify-center gap-3 p-3">
              <div className="w-10 h-10 rounded-full bg-white/15 flex items-center justify-center">
                <div className="w-4 h-4 rounded-full border-2 border-white/70" />
              </div>
              <p className="font-display font-semibold text-white text-[10px] tracking-wide text-center leading-tight">
                {book.label}
              </p>
              <div className="w-14 h-px bg-white/25" />
              <p className="text-white/50 text-[8px] tracking-widest">EXERCISE BOOK</p>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function LoginScene() {
  const containerRef = useRef(null)
  const [reduceMotion, setReduceMotion] = useState(false)
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const tiltX = useSpring(rawX, { stiffness: 80, damping: 20 })
  const tiltY = useSpring(rawY, { stiffness: 80, damping: 20 })

  useEffect(() => {
    // matchMedia isn't guaranteed on every WebView this might run in
    // (older/low-end Android targets, specifically called out in this
    // project's brief), fail safe to "motion is fine" rather than crash.
    if (typeof window.matchMedia !== 'function') return
    try {
      const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
      setReduceMotion(mq.matches)
      const handler = (e) => setReduceMotion(e.matches)
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    } catch {
      // ignore, same fail-safe as above
    }
  }, [])

  const handlePointerMove = (e) => {
    if (reduceMotion || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width - 0.5
    const py = (e.clientY - rect.top) / rect.height - 0.5
    rawX.set(px * 30)
    rawY.set(py * 20)
  }
  const handlePointerLeave = () => { rawX.set(0); rawY.set(0) }

  return (
    <div
      ref={containerRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      className="w-full h-full relative"
      style={{ perspective: '1400px' }}
    >
      <div className="absolute inset-0" style={{ transformStyle: 'preserve-3d' }}>
        {BOOKS.map((book, i) => (
          <Copybook key={book.label} book={book} index={i} tiltX={tiltX} tiltY={tiltY} />
        ))}
      </div>
      {/* Ambient ground shadow for grounding depth cues */}
      <div
        className="absolute left-1/2 top-1/2 w-72 h-20 -translate-x-1/2 rounded-full opacity-40"
        style={{ background: 'radial-gradient(ellipse, rgba(0,0,0,0.5), transparent 70%)', transform: 'translateZ(-100px) translateY(90px)' }}
      />
    </div>
  )
}
