import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../../..')
const backendDir = path.join(repoRoot, 'backend')
const apiPort = process.env.PLAYWRIGHT_API_PORT || '8001'

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

function forwardSignal(signal) {
  for (const child of childProcesses) {
    if (!child.killed) child.kill(signal)
  }
}

process.on('SIGINT', () => forwardSignal('SIGINT'))
process.on('SIGTERM', () => forwardSignal('SIGTERM'))

await runSetup()

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
