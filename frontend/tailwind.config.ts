import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gets: {
          red: "#CC0000",
        },
      },
      fontFamily: {
        jakarta: ["var(--font-jakarta)"],
      },
    },
  },
  plugins: [],
};
export default config;
