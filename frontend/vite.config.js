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
    },
    build: {
        chunkSizeWarningLimit: 900,
        rollupOptions: {
            output: {
                manualChunks: {
                    react: ["react", "react-dom", "react-router-dom"],
                    forms: ["@hookform/resolvers", "react-hook-form", "zod"],
                    data: ["@tanstack/react-table", "date-fns", "react-virtuoso", "zustand"],
                    ui: [
                        "@radix-ui/react-alert-dialog",
                        "@radix-ui/react-avatar",
                        "@radix-ui/react-checkbox",
                        "@radix-ui/react-dialog",
                        "@radix-ui/react-dropdown-menu",
                        "@radix-ui/react-label",
                        "@radix-ui/react-progress",
                        "@radix-ui/react-select",
                        "@radix-ui/react-separator",
                        "@radix-ui/react-slot",
                        "@radix-ui/react-tabs",
                        "@radix-ui/react-tooltip",
                        "lucide-react"
                    ],
                    charts: ["recharts"],
                    markdown: ["react-markdown", "remark-gfm"],
                    syntax: ["react-syntax-highlighter"]
                }
            }
        }
    }
    };
});
