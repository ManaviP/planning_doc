import { useEffect, useRef } from 'react';
import gsap from 'gsap';

export default function CountMetric({ value }) {
  const nodeRef = useRef(null);
  const numericValue = Number(value) || 0;
  const decimals = Number.isInteger(numericValue) ? 0 : 1;

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }

    const state = { current: 0 };
    const tween = gsap.to(state, {
      current: numericValue,
      duration: 1.1,
      ease: 'power3.out',
      onUpdate: () => {
        node.textContent = state.current.toFixed(decimals);
      },
    });

    return () => tween.kill();
  }, [decimals, numericValue]);

  return <span ref={nodeRef}>{numericValue.toFixed(decimals)}</span>;
}
