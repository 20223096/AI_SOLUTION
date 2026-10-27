import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 개발 서버는 /api 요청을 백엔드로 프록시한다. 브라우저 입장에서는 같은 origin이라 CORS가 생기지 않는다.
  const apiTarget = (env.VITE_SHH_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

  return {
    plugins: [react()],
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
