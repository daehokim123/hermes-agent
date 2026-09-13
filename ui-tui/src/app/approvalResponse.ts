import type { ApprovalRespondResponse } from '../gatewayTypes.js'

import { getOverlayState, patchOverlayState } from './overlayStore.js'
import { patchTurnState } from './turnStore.js'
import { getUiState, patchUiState } from './uiStore.js'

type ApprovalRpc = (method: string, params: Record<string, unknown>) => Promise<ApprovalRespondResponse | null>

// Shared by prompt choices and Ctrl-C: never let a late reply dismiss a newer prompt.
export async function respondToApproval(rpc: ApprovalRpc, choice: string) {
  const answered = getOverlayState().approval
  const sid = getUiState().sid

  if (!answered || (answered.sessionId && answered.sessionId !== sid)) {
    return
  }

  const response = await rpc('approval.respond', {
    choice,
    session_id: sid,
    ...(answered.requestId ? { request_id: answered.requestId } : {})
  })

  const current = getOverlayState().approval

  if (
    getUiState().sid !== sid ||
    !current ||
    (answered.requestId ? current.requestId !== answered.requestId : current !== answered)
  ) {
    return
  }

  if (!response) {
    return
  }

  const resolved = response.resolved === undefined ? response.ok !== false : response.resolved > 0

  if (!resolved) {
    if (response.resolved === 0) {
      patchOverlayState({ approval: null })
      patchUiState({ status: 'approval expired or already resolved' })
    }

    return
  }

  patchOverlayState({ approval: null })
  patchTurnState({ outcome: choice === 'deny' ? 'denied' : `approved (${choice})` })
  patchUiState({ status: 'running…' })
}
