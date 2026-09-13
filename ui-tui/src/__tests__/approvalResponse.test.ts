import { beforeEach, expect, it, vi } from 'vitest'

import { respondToApproval } from '../app/approvalResponse.js'
import { getOverlayState, patchOverlayState, resetOverlayState } from '../app/overlayStore.js'
import { getTurnState, resetTurnState } from '../app/turnStore.js'
import { getUiState, patchUiState, resetUiState } from '../app/uiStore.js'
beforeEach(() => {
  resetOverlayState()
  resetUiState()
  resetTurnState()
  patchUiState({ sid: 's' })
})
it.each(['once', 'deny'])('correlates %s and treats resolved zero as stale, not success', async choice => {
  const approval = { requestId: 'r', sessionId: 's', command: 'secret', description: 'secret' }
  patchOverlayState({ approval })
  const rpc = vi.fn(async () => ({ resolved: 0 }))
  await respondToApproval(rpc as any, choice)
  expect(rpc).toHaveBeenCalledWith('approval.respond', { choice, request_id: 'r', session_id: 's' })
  expect(getOverlayState().approval).toBeNull()
  expect(getTurnState().outcome).not.toContain('approved')
  expect(getUiState().status).toContain('expired')
})
it.each(['once', 'deny'])('keeps replacement modal and session state when %s reply arrives late', async choice => {
  const old = { requestId: 'r', sessionId: 's', command: 'old', description: '' }
  patchOverlayState({ approval: old })
  let resolve!: (r: any) => void
  const rpc = vi.fn(
    () =>
      new Promise(r => {
        resolve = r
      })
  )
  const pending = respondToApproval(rpc as any, choice)
  const replacement = { ...old, requestId: 'new' }
  patchOverlayState({ approval: replacement })
  patchUiState({ status: 'approval needed' })
  resolve({ resolved: 1 })
  await pending
  expect(getOverlayState().approval).toBe(replacement)
  expect(getUiState().status).toBe('approval needed')
})
it('does not send an approval from a different active session', async () => {
  patchOverlayState({ approval: { requestId: 'r', sessionId: 'foreign', command: '', description: '' } })
  const rpc = vi.fn()
  await respondToApproval(rpc as any, 'once')
  expect(rpc).not.toHaveBeenCalled()
})
