/**
 * Largest of `xs` and `floor`, by a loop: `Math.max(...xs)` spreads every
 * element onto the call stack and throws RangeError near 10^5 elements,
 * which a long trace reaches.
 * @param {Iterable<number>} xs
 * @param {number} [floor] returned when `xs` is empty or all smaller
 * @returns {number}
 */
export function maxOf(xs, floor = -Infinity) {
  let m = floor;
  for (const x of xs) if (x > m) m = x;
  return m;
}
