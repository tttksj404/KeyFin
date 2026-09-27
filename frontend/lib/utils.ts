import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

import { size, typography } from "@/lib/theme";

const typographyTokens = Object.keys(typography);
const sizeTokens = Object.keys(size);

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: typographyTokens }],
      h: [{ h: sizeTokens }],
      "min-h": [{ "min-h": sizeTokens }],
      w: [{ w: sizeTokens }],
      "min-w": [{ "min-w": sizeTokens }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
