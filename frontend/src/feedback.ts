import { createToaster } from '@ark-ui/react/toast'

/* ================================================================== *
 * Toast + confirm-action engines.
 * Kept outside component files so Fast Refresh keeps working; the
 * hosts that render them live in ui.tsx and App.
 * ================================================================== */

export const toaster = createToaster({ placement: 'bottom-end', gap: 12, max: 3 })

export const notify = {
  success: (title: string, description?: string) => toaster.create({ title, description, type: 'success' }),
  error: (title: string, description?: string) => toaster.create({ title, description, type: 'error', duration: 7000 }),
  info: (title: string, description?: string) => toaster.create({ title, description, type: 'info' }),
}

export interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>
let confirmImpl: ConfirmFn | null = null

/** Registered by <ConfirmHost />; falls back to window.confirm if absent. */
export function setConfirmHandler(fn: ConfirmFn | null): void {
  confirmImpl = fn
}

export function confirmAction(opts: ConfirmOptions): Promise<boolean> {
  return confirmImpl ? confirmImpl(opts) : Promise.resolve(window.confirm(opts.title))
}
