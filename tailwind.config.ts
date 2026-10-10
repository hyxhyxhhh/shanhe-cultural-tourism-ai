import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#162724",
        forest: "#17372f",
        pine: "#244f45",
        moss: "#52786d",
        canvas: "#f3f5f1",
        line: "#e2e6e2",
        gold: "#c5a76b",
        mist: "#edf2ef"
      },
      boxShadow: { card: "0 1px 2px rgba(22,39,36,.035)" },
      borderRadius: { card: "10px" }
    }
  },
  plugins: []
};

export default config;
