// Centralized motion tokens — physical, weight-based easing adapted from Second Self's DESIGN.md
// (SwiftUI spring(response, dampingFraction) → CSS cubic-bezier + duration). No linear easing, ever.
// The matching CSS custom properties live in style.css (:root) and are the source used by classes;
// these exports are for any inline React transitions that want the same feel.

export const spring = {
  panel:     {easing: 'cubic-bezier(.22,1,.36,1)',    duration: 420}, // ssPanelSpring  (.3/.85)
  reveal:    {easing: 'cubic-bezier(.2,.9,.3,1)',     duration: 320}, // ssContentReveal(.25/.88)
  message:   {easing: 'cubic-bezier(.25,.9,.3,1)',    duration: 360}, // ssMessageEntrance(.3/.9)
  micro:     {easing: 'cubic-bezier(.3,1.2,.5,1)',    duration: 200}, // ssMicro        (.2/.85)
  character: {easing: 'cubic-bezier(.34,1.56,.64,1)', duration: 380}, // ssCharacterTransition(.3/.85)
} as const;

export type SpringName = keyof typeof spring;

/** `transition` string for a property using a named spring, e.g. transitionFor('transform','micro'). */
export function transitionFor(property: string, name: SpringName): string {
  const {easing, duration} = spring[name];
  return `${property} ${duration}ms ${easing}`;
}
