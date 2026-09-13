import { beforeEach, expect, it, vi } from 'vitest'
// Terminal paint is not part of the approval protocol; no Ink build needed.
vi.mock('@hermes/ink', () => ({ forceRedraw: vi.fn(), onTerminalBackground: vi.fn(), onTerminalForeground: vi.fn() }))
import { createGatewayEventHandler } from '../app/createGatewayEventHandler.js'
import { getOverlayState, resetOverlayState } from '../app/overlayStore.js'
import { patchUiState, resetUiState } from '../app/uiStore.js'

beforeEach(() => {
  resetOverlayState()
  resetUiState()
})
it('rejects foreign/no-active session approvals and preserves exact accepted identity', () => {
  const onEvent = createGatewayEventHandler({
    composer: {},
    gateway: {},
    session: {},
    submission: {},
    system: {},
    transcript: {},
    voice: {}
  } as any)

  const event = {
    type: 'approval.request',
    session_id: 'focused',
    payload: {
      request_id: 'exact-request',
      command: 'sensitive-command',
      description: 'sensitive-description'
    }
  } as any

  onEvent(event)
  expect(getOverlayState().approval).toBeNull()
  patchUiState({ sid: 'other' })
  onEvent(event)
  expect(getOverlayState().approval).toBeNull()
  patchUiState({ sid: 'focused' })
  onEvent(event)
  expect(getOverlayState().approval).toMatchObject({ requestId: 'exact-request', sessionId: 'focused' })
})
