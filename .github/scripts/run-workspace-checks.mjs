// Run every workspace check at the same time and report all failures.
//
// The unit of work is a CHECK, and not a workspace. A package that declares
// `check:*` sub-scripts gives one unit for each sub-script. A package with a
// plain `check` gives that. This is the same selection rule the old CI matrix
// used, so the set of commands is unchanged. Only the schedule is different.
//
// This is not `npm run --ws check`, because that command is serial and stops
// at the first workspace that fails. This runs every unit and fails at the
// end with the full list.
//
// The output of each unit goes to a buffer and prints on completion inside a
// group that collapses. Children that write to one stdout together interleave
// their lines, and a failure is then hard to read.
//
// This also runs on a laptop: `node .github/scripts/run-workspace-checks.mjs`.
// `--concurrency N` sets the limit. `--only package::script` selects one unit
// for an isolated receipt. `--list` prints the selected units and exits.

import { execFileSync, spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { availableParallelism } from 'node:os'
import { join } from 'node:path'
import { finished } from 'node:stream/promises'
import { pathToFileURL } from 'node:url'

const IS_CI = Boolean(process.env.GITHUB_ACTIONS)
const NPM = process.platform === 'win32' ? 'npm.cmd' : 'npm'

/** @returns {{pkg: string, script: string}[]} */
function discoverUnits() {
  const raw = execFileSync(NPM, ['query', '.workspace'], {
    encoding: 'utf-8',
    shell: process.platform === 'win32',
  })
  /** @type {{location: string, scripts?: Record<string,string>}[]} */
  const pkgs = JSON.parse(raw)

  /** @type {{pkg: string, script: string}[]} */
  const units = []
  for (const pkg of pkgs) {
    const scripts = pkg.scripts || {}
    const subs = Object.keys(scripts).filter((s) => /^check:.+$/.test(s))
    if (subs.length > 0) {
      for (const script of subs) units.push({ pkg: pkg.location, script })
    } else if (scripts.check) {
      units.push({ pkg: pkg.location, script: 'check' })
    }
  }
  return units
}

/** @param {{pkg: string, script: string}} unit */
export function collectChildResult(child, unit, started) {
  return new Promise((resolve) => {
    /** @type {Buffer[]} */
    const stdoutChunks = []
    /** @type {Buffer[]} */
    const stderrChunks = []
    child.stdout.on('data', (c) => stdoutChunks.push(c))
    child.stderr.on('data', (c) => stderrChunks.push(c))
    const stdoutFinished = finished(child.stdout).catch((error) => error)
    const stderrFinished = finished(child.stderr).catch((error) => error)
    let spawnError = null
    child.on('error', (err) => {
      spawnError = err
    })
    child.on('close', async (code, signal) => {
      const streamErrors = (await Promise.all([stdoutFinished, stderrFinished])).filter(Boolean)
      if (spawnError) stderrChunks.push(Buffer.from(`failed to spawn: ${spawnError.message}\n`))
      for (const error of streamErrors) {
        stderrChunks.push(Buffer.from(`failed to drain child output: ${error.message}\n`))
      }
      resolve({
        unit,
        code: code ?? 1,
        signal,
        stdout: Buffer.concat(stdoutChunks).toString('utf-8'),
        stderr: Buffer.concat(stderrChunks).toString('utf-8'),
        ms: Date.now() - started,
      })
    })
  })
}

/** @param {{pkg: string, script: string}} unit */
function runUnit(unit) {
  const started = Date.now()
  const child = spawn(NPM, ['run', '--prefix', unit.pkg, unit.script], {
    // Buffer, and do not inherit. Children that share one stdout
    // interleave their lines, and a failure is then hard to read.
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
  })
  return collectChildResult(child, unit, started)
}

function logFilename(unit) {
  return `${unit.pkg}--${unit.script}`.replaceAll(/[^A-Za-z0-9_.-]/g, '_')
}

async function writeResultLogs(logDir, result) {
  await mkdir(logDir, { recursive: true })
  const base = join(logDir, logFilename(result.unit))
  await Promise.all([
    writeFile(`${base}.stdout.log`, result.stdout),
    writeFile(`${base}.stderr.log`, result.stderr),
    writeFile(`${base}.result.json`, `${JSON.stringify({
      ...result.unit,
      code: result.code,
      signal: result.signal,
      ms: result.ms,
    }, null, 2)}\n`),
  ])
}

export async function main() {
  const argv = process.argv.slice(2)
  const discoveredUnits = discoverUnits()
  const onlyIdx = argv.indexOf('--only')
  const only = onlyIdx === -1 ? null : argv[onlyIdx + 1]
  if (onlyIdx !== -1 && !only) {
    console.error('::error::--only requires a package::script value.')
    process.exitCode = 1
    return
  }
  const units = only
    ? discoveredUnits.filter((unit) => `${unit.pkg}::${unit.script}` === only)
    : discoveredUnits
  const logDir = process.env.RUNNER_TEMP ? join(process.env.RUNNER_TEMP, 'workspace-check-logs') : null

  if (units.length === 0) {
    console.error(
      only
        ? `::error::No workspace check matches --only ${only}.`
        : '::error::No workspace package declares a check script — refusing to report green having run nothing.',
    )
    process.exit(1)
  }

  if (argv.includes('--list')) {
    for (const u of units) console.log(`${u.pkg} :: ${u.script}`)
    return
  }

  const flagIdx = argv.indexOf('--concurrency')
  const concurrency = Math.max(
    1,
    flagIdx !== -1 ? Number(argv[flagIdx + 1]) : Math.min(units.length, availableParallelism()),
  )

  console.log(`running ${units.length} checks, up to ${concurrency} at a time:`)
  for (const u of units) console.log(`  ${u.pkg} :: ${u.script}`)
  console.log('')

  const queue = [...units]
  /** @type {{unit: {pkg: string, script: string}, code: number, signal: string|null, stdout: string, stderr: string, ms: number}[]} */
  const results = []

  async function worker() {
    for (;;) {
      const unit = queue.shift()
      if (!unit) return
      const res = await runUnit(unit)
      results.push(res)
      if (logDir) await writeResultLogs(logDir, res)
      const label = `${res.unit.pkg} :: ${res.unit.script}`
      const secs = (res.ms / 1000).toFixed(1)
      const status = res.code === 0 ? 'PASS' : 'FAIL'
      if (IS_CI) console.log(`::group::${status} ${label} (${secs}s)`)
      else console.log(`----- ${status} ${label} (${secs}s) -----`)
      if (res.stdout) process.stdout.write(res.stdout.endsWith('\n') ? res.stdout : res.stdout + '\n')
      if (res.stderr) process.stderr.write(res.stderr.endsWith('\n') ? res.stderr : res.stderr + '\n')
      if (res.signal) console.error(`child terminated by signal ${res.signal}`)
      if (IS_CI) console.log('::endgroup::')
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, units.length) }, worker))

  const failed = results.filter((r) => r.code !== 0)
  console.log('\n=== summary ===')
  for (const r of [...results].sort((a, b) => b.ms - a.ms)) {
    console.log(
      `  ${r.code === 0 ? 'pass' : 'FAIL'}  ${(r.ms / 1000).toFixed(1).padStart(6)}s  ${r.unit.pkg} :: ${r.unit.script}`,
    )
  }

  if (failed.length > 0) {
    for (const r of failed) {
      const outcome = r.signal ? `signal ${r.signal}` : `exit code ${r.code}`
      console.error(`::error::${r.unit.pkg} :: ${r.unit.script} failed (${outcome})`)
    }
    console.error(`::error::${failed.length} of ${results.length} checks failed`)
    process.exitCode = 1
    return
  }
  console.log(`\nall ${results.length} checks passed`)
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main()
}
