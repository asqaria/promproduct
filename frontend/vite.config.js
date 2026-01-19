import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

const certDir = path.resolve(__dirname, "certs");
const httpsOptions = fs.existsSync(certDir)
  ? {
      key: fs.readFileSync(path.join(certDir, "key.pem")),
      cert: fs.readFileSync(path.join(certDir, "cert.pem")),
    }
  : false;

export default defineConfig({
  plugins: [react()],
  server: {
    https: httpsOptions || true, // true falls back to self-signed
    host: true,                  // listen on all interfaces
    port: 5173,
  },
  preview: {
    https: httpsOptions || true,
    host: true,
    port: 4173,
  },
});