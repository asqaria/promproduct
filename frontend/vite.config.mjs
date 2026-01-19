import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const certDir = resolve(__dirname, "certs");
const httpsOptions = fs.existsSync(certDir)
  ? {
      key: fs.readFileSync(resolve(certDir, "key.pem")),
      cert: fs.readFileSync(resolve(certDir, "cert.pem")),
    }
  : true; // fallback to self-signed

export default defineConfig({
  plugins: [react()],
  server: {
    https: httpsOptions,
    host: true,
    port: 5173,
  },
  preview: {
    https: httpsOptions,
    host: true,
    port: 4173,
  },
});