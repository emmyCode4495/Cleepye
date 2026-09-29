import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const ENGINE = process.env.CLEEPYE_API ?? "http://127.0.0.1:8741";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": ENGINE,
      "/health": ENGINE,
    },
  },
});
