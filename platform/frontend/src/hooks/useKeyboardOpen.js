import { useEffect, useState } from 'react';

// The on-screen keyboard shrinks the visual viewport; a bar fixed to the bottom would ride on top of it.
// Considered open when the visual viewport is shorter than the layout viewport by more than this.
export const KEYBOARD_THRESHOLD_PX = 150;

export function useKeyboardOpen() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return undefined;
    // Pinch zoom also shrinks the visual viewport; only an unzoomed viewport means the keyboard.
    const update = () =>
      setOpen(
        (viewport.scale ?? 1) <= 1 && window.innerHeight - viewport.height > KEYBOARD_THRESHOLD_PX,
      );
    update();
    viewport.addEventListener('resize', update);
    return () => viewport.removeEventListener('resize', update);
  }, []);

  return open;
}
