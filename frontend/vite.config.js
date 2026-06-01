import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");
    const host = env.VITE_DEV_HOST || "127.0.0.1";
    const port = Number(env.VITE_DEV_PORT || 5173);
    const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:9090";
    return {
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src")
        }
    },
    server: {
        host,
        port,
        proxy: {
            "/api": {
                target: proxyTarget,
                changeOrigin: true,
                secure: false
            }
        }
    }
    };
});
