import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const legacyEnv = loadEnv(mode, process.cwd(), '')
  const frontendEnv = loadEnv(mode, `${process.cwd()}/frontend`, '')
  const apiBaseUrl = frontendEnv.VITE_SHH_API_BASE_URL || legacyEnv.VITE_SHH_API_BASE_URL || 'http://127.0.0.1:8000'
  // 개발 서버는 /api 요청을 백엔드로 프록시한다. 브라우저 입장에서는 같은 origin이라 CORS가 생기지 않는다.
  const apiTarget = apiBaseUrl.replace(/\/+$/, '')

  return {
    plugins: [react()],
    // Frontend settings live under frontend/.env.local. The root file is a migration fallback only.
    define: { 'import.meta.env.VITE_SHH_API_BASE_URL': JSON.stringify(apiTarget) },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
