/**
 * Visual approximations of the ASS caption styles defined in backend/core/captions.py.
 * The backend remains the source of truth for the ids; anything it returns that we
 * don't know about falls back to DEFAULT_LOOK so new styles still show up.
 */
export interface CaptionLook {
  id: string;
  name: string;
  blurb: string;
  font: string;
  weight: number;
  size: number; // relative scale, 1 = viral
  primary: string;
  highlight: string;
  outline: number;
  uppercase?: boolean;
}

const ARIAL = 'Arial, "Helvetica Neue", Helvetica, sans-serif';

export const CAPTION_LOOKS: CaptionLook[] = [
  { id: "viral", name: "Viral", blurb: "Big white text; the word being spoken pops in yellow. The go-to for TikTok, Reels and Shorts.", font: ARIAL, weight: 800, size: 1, primary: "#ffffff", highlight: "#ffff00", outline: 3 },
  { id: "clean", name: "Clean", blurb: "Medium white text with a soft outline and no colour changes. Easy to read on any footage.", font: ARIAL, weight: 700, size: 0.82, primary: "#ffffff", highlight: "#ffffff", outline: 2 },
  { id: "karaoke", name: "Karaoke", blurb: "Heavy, wide lettering that sweeps word by word like a sing-along. Best for music, hype and fast talkers.", font: '"Arial Black", Arial, sans-serif', weight: 900, size: 0.94, primary: "#cccccc", highlight: "#ffff00", outline: 3 },
  { id: "bold", name: "Bold", blurb: "Condensed, all-caps headline type with an orange highlight. Loud and punchy for strong opinions.", font: 'Impact, "Arial Narrow", Haettenschweiler, sans-serif', weight: 400, size: 1.08, primary: "#ffffff", highlight: "#ffa500", outline: 4, uppercase: true },
  { id: "neon", name: "Neon", blurb: "White text with a magenta highlight on each spoken word. Suits late-night, gaming and tech content.", font: ARIAL, weight: 800, size: 0.97, primary: "#ffffff", highlight: "#ff00ff", outline: 3 },
  { id: "minimal", name: "Minimal", blurb: "Small, thin, understated text with no colour shift. Keeps the focus on the video for interviews and talks.", font: 'Helvetica, "Helvetica Neue", Arial, sans-serif', weight: 500, size: 0.74, primary: "#ffffff", highlight: "#ffffff", outline: 1 },
  { id: "pop", name: "Pop", blurb: "Playful yellow text with a red highlight. Works for comedy, lifestyle and casual content.", font: '"Comic Sans MS", "Comic Neue", "Chalkboard SE", cursive', weight: 700, size: 0.9, primary: "#ffff00", highlight: "#ff0000", outline: 3 },
];

const DEFAULT_LOOK: CaptionLook = { ...CAPTION_LOOKS[0], id: "custom", name: "Custom", blurb: "Custom caption style." };

export function getLook(id: string, name?: string): CaptionLook {
  const known = CAPTION_LOOKS.find((s) => s.id === id);
  if (known) return known;
  return { ...DEFAULT_LOOK, id, name: name ?? id.charAt(0).toUpperCase() + id.slice(1) };
}

/** Merge the API's style list with our known looks (API order wins, extras kept). */
export function mergeStyles(apiStyles: Array<{ id: string; name: string }> | null): CaptionLook[] {
  if (!apiStyles?.length) return CAPTION_LOOKS;
  return apiStyles.map((s) => getLook(s.id, s.name));
}

/** text-shadow stroke, sized in a CSS length unit so it scales with the preview. */
export function outlineShadow(size: string): string {
  return [`${size} 0 #000`, `-${size} 0 #000`, `0 ${size} #000`, `0 -${size} #000`, `${size} ${size} #000`, `-${size} -${size} #000`, `${size} -${size} #000`, `-${size} ${size} #000`].join(",");
}
