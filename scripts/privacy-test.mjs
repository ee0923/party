import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { stripTypeScriptTypes } from 'node:module'
import path from 'node:path'
import vm from 'node:vm'

const root = process.argv[2]
const output = []
const files = []
let failWrite = false
const context = vm.createContext({
  Date,
  console: Object.fromEntries(['log', 'debug', 'warn', 'error'].map((level) => [level, (...args) => output.push(args)]))
})
function stub(exports) {
  return new vm.SyntheticModule(Object.keys(exports), function () {
    for (const [key, value] of Object.entries(exports)) this.setExport(key, value)
  }, { context })
}
async function load(name, imports) {
  const source = await readFile(path.join(root, name), 'utf8')
  const module = new vm.SourceTextModule(stripTypeScriptTypes(source), { context })
  await module.link((specifier) => {
    assert.ok(Object.hasOwn(imports, specifier), `Unexpected import: ${specifier}`)
    return stub(imports[specifier])
  })
  await module.evaluate()
  return module.namespace
}
const logger = await load('src/main/utils/logger.ts', {
  './dirs': { logPath: () => '/test.log' },
  './logFile': { appendToFileWithLimit: async (_file, text) => {
    if (failWrite) throw new Error('private-write-error')
    files.push(text)
  } }
})
const log = logger.createLogger('test')
for (const level of ['debug', 'info', 'warn', 'error', 'log']) {
  await log[level]('https://private.example/?token=secret-token', new Error('private-password'))
}
assert.equal(files.length, 5)
assert.equal(output.length, 5)
assert.match(files.join(''), /Application event/)
assert.doesNotMatch(JSON.stringify([files, output]), /secret-token|private-password|private\.example/)
failWrite = true
await log.error('secret-token', new Error('private-password'))
assert.doesNotMatch(JSON.stringify(output), /private-write-error|secret-token|private-password/)
logger.setAppLogDisabled(true)
await log.info('secret-token')
assert.equal(files.length, 5)
const component = await load('src/renderer/src/components/updater/updater-button.tsx', { react: { default: {} } })
assert.equal(component.default({ iconOnly: false, autoCheckUpdate: true }), null)
assert.equal(component.default({ iconOnly: true }), null)
console.log('Clash Party: background updater has no network imports; application file, console and write-failure diagnostics redact payloads')
