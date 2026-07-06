import { spawn } from 'node:child_process'
import net from 'node:net'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../../..')
const backendDir = path.join(repoRoot, 'backend')
const apiPort = process.env.PLAYWRIGHT_API_PORT || '8001'
const redisPort = process.env.PLAYWRIGHT_REDIS_PORT || '6390'

const env = {
  ...process.env,
  APP_ENV: process.env.APP_ENV || 'development',
  DATABASE_URL: process.env.DATABASE_URL || 'sqlite:///runtime/e2e/conversations.db',
  DATA_DIR: process.env.DATA_DIR || 'runtime/e2e',
  CHROMA_PERSIST_DIR: process.env.CHROMA_PERSIST_DIR || 'runtime/e2e/chroma_db',
  CHECKPOINT_DB_PATH: process.env.CHECKPOINT_DB_PATH || 'runtime/e2e/checkpoints.db',
  JWT_SECRET: process.env.JWT_SECRET || 'e2e-jwt-secret-1234567890abcdef',
  SILICONFLOW_API_KEY: process.env.SILICONFLOW_API_KEY || '',
  TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
  REDIS_URL: process.env.REDIS_URL || `redis://127.0.0.1:${redisPort}/0`,
  AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: process.env.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE || '30',
  KNOWBASE_E2E_FAKE_AI: process.env.KNOWBASE_E2E_FAKE_AI || 'true',
}

const childProcesses = []
const uvCommand = process.platform === 'win32' ? 'uv.exe' : 'uv'

function spawnCommand(command, args, options = {}) {
  return spawn(command, args, {
    cwd: backendDir,
    env,
    stdio: 'inherit',
    ...options,
  })
}

function runSetup() {
  return new Promise((resolve, reject) => {
    const setup = spawnCommand(uvCommand, ['run', 'python', 'scripts/prepare_e2e_env.py'])
    setup.on('exit', (code) => {
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error(`prepare_e2e_env.py failed with exit code ${code ?? 'unknown'}`))
    })
  })
}

function waitForPort(port, host = '127.0.0.1', timeoutMs = 10000) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    const tryConnect = () => {
      const socket = new net.Socket()
      socket
        .once('connect', () => {
          socket.destroy()
          resolve()
        })
        .once('error', () => {
          socket.destroy()
          if (Date.now() - startedAt > timeoutMs) {
            reject(new Error(`Timed out waiting for ${host}:${port}`))
            return
          }
          setTimeout(tryConnect, 200)
        })
        .connect(Number(port), host)
    }

    tryConnect()
  })
}

function forwardSignal(signal) {
  for (const child of childProcesses) {
    if (!child.killed) child.kill(signal)
  }
}

process.on('SIGINT', () => forwardSignal('SIGINT'))
process.on('SIGTERM', () => forwardSignal('SIGTERM'))

await runSetup()

const fakeRedis = spawnCommand(uvCommand, ['run', 'python', 'scripts/start_fake_redis.py'])
childProcesses.push(fakeRedis)
await waitForPort(redisPort)

const worker = spawnCommand(uvCommand, ['run', 'python', 'scripts/run_e2e_worker.py'])
childProcesses.push(worker)

const server = spawnCommand(uvCommand, [
  'run',
  'uvicorn',
  'src.api.main:app',
  '--host',
  '127.0.0.1',
  '--port',
  apiPort,
])
childProcesses.push(server)

server.on('exit', (code) => {
  process.exit(code ?? 0)
})
