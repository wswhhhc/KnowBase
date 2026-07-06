import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(__dirname, '..', '..')
const appPort = process.env.PLAYWRIGHT_APP_PORT || '4173'
const apiPort = process.env.PLAYWRIGHT_API_PORT || '8001'
const child = process.platform === 'win32'
  ? spawn(
      process.env.ComSpec || 'cmd.exe',
      ['/d', '/s', '/c', `npm run dev -- --host 127.0.0.1 --port ${appPort}`],
      {
        cwd: frontendDir,
        env: {
          ...process.env,
          VITE_API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`,
        },
        stdio: 'inherit',
      },
    )
  : spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', appPort], {
      cwd: frontendDir,
      env: {
        ...process.env,
        VITE_API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`,
      },
      stdio: 'inherit',
    })

process.on('SIGINT', () => child.kill('SIGINT'))
process.on('SIGTERM', () => child.kill('SIGTERM'))

child.on('exit', (code) => {
  process.exit(code ?? 0)
})
