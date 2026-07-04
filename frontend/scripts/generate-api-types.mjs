import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const frontendRoot = resolve(__dirname, '..')
const backendOpenapiPath = resolve(frontendRoot, '..', 'backend', 'openapi.json')
const outputPath = resolve(frontendRoot, 'src', 'shared', 'api', 'api-types.openapi.ts')
const cliPath = resolve(frontendRoot, 'node_modules', 'openapi-typescript', 'bin', 'cli.js')
const tempDir = resolve(frontendRoot, '.generated')
const tempOpenapiPath = resolve(tempDir, 'openapi.normalized.json')

function dereferenceLocalSchema(ref, components) {
  const prefix = '#/components/schemas/'
  if (!ref.startsWith(prefix)) {
    return null
  }

  const schemaName = ref.slice(prefix.length)
  return components?.schemas?.[schemaName] ?? null
}

function inlineProblematicResponseRefs(document) {
  const schema =
    document.paths?.['/api/knowledge-base/chunks/{chunk_id}']?.get?.responses?.['200']?.content?.['application/json']?.schema
  if (!schema || typeof schema !== 'object' || !('$ref' in schema)) {
    return document
  }

  const resolved = dereferenceLocalSchema(schema.$ref, document.components)
  if (resolved) {
    document.paths['/api/knowledge-base/chunks/{chunk_id}'].get.responses['200'].content['application/json'].schema =
      structuredClone(resolved)
  }

  return document
}

const source = JSON.parse(readFileSync(backendOpenapiPath, 'utf8'))
const normalized = inlineProblematicResponseRefs(source)

mkdirSync(tempDir, { recursive: true })
writeFileSync(tempOpenapiPath, JSON.stringify(normalized, null, 2), 'utf8')

try {
  execFileSync(
    process.execPath,
    [cliPath, tempOpenapiPath, '--output', outputPath],
    { stdio: 'inherit', cwd: frontendRoot },
  )
} finally {
  rmSync(tempOpenapiPath, { force: true })
}
