import { EventEmitter } from 'node:events'
import { PassThrough } from 'node:stream'

import { expect, it } from 'vitest'

it('preserves separate output and the terminating signal after both streams drain', async () => {
  const modulePath = new URL('../.github/scripts/run-workspace-checks.mjs', import.meta.url).href
  const { collectChildResult } = await import(/* @vite-ignore */ modulePath)
  const stdout = new PassThrough()
  const stderr = new PassThrough()
  const child = Object.assign(new EventEmitter(), { stdout, stderr })
  const completion = collectChildResult(child, { pkg: 'fixture', script: 'check' }, Date.now())

  stdout.write('stdout-before-close\n')
  stderr.write('stderr-before-close\n')
  child.emit('close', null, 'SIGTERM')
  let resolved = false
  void completion.then(() => { resolved = true })
  await Promise.resolve()
  expect(resolved).toBe(false)

  stdout.end('stdout-after-close\n')
  stderr.end('stderr-after-close\n')
  const result = await completion
  expect(result.code).toBe(1)
  expect(result.signal).toBe('SIGTERM')
  expect(result.stdout).toBe('stdout-before-close\nstdout-after-close\n')
  expect(result.stderr).toBe('stderr-before-close\nstderr-after-close\n')
})