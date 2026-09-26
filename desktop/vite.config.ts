import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import electron from "vite-plugin-electron/simple";
import renderer from "vite-plugin-electron-renderer";

export default defineConfig({
  plugins: [
    react(),

    electron({
      main: {
        entry: "electron/main.ts",
      },

      preload: {
        input: "electron/preload.ts",
      },

      renderer: {},
    }),

    renderer(),
  ],

  server: {
    port: 5173,
    strictPort: true,
  },
});