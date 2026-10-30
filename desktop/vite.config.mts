import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import electron from "vite-plugin-electron/simple";

export default defineConfig({
  plugins: [
    react(),

    // Tailwind CSS v4
    tailwindcss(),

    // Electron main + preload
    electron({
      main: {
        entry: "electron/main.ts",
        onstart({ startup }) {
          const electronEnv = { ...process.env };
          delete electronEnv.ELECTRON_RUN_AS_NODE;
          void startup(undefined, { env: electronEnv });
        },
      },
      preload: {
        input: "electron/preload.ts",
      },
      renderer: {},
    }),
  ],

  server: {
    port: 5173,
    strictPort: true,
  },
});
