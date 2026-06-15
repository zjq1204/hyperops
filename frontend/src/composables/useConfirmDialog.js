import { reactive } from 'vue'

export function useConfirmDialog() {
  const confirmDialog = reactive({
    show: false,
    title: '',
    message: '',
    confirmText: '',
    variant: 'danger',
    loading: false,
    onConfirm: null
  })

  function requestConfirm({
    title = '',
    message = '',
    confirmText = '',
    variant = 'danger',
    onConfirm
  }) {
    confirmDialog.show = true
    confirmDialog.title = title
    confirmDialog.message = message
    confirmDialog.confirmText = confirmText
    confirmDialog.variant = variant
    confirmDialog.loading = false
    confirmDialog.onConfirm = onConfirm
  }

  function closeConfirmDialog() {
    if (confirmDialog.loading) return
    confirmDialog.show = false
    confirmDialog.onConfirm = null
  }

  async function runConfirmedAction() {
    if (!confirmDialog.onConfirm) {
      closeConfirmDialog()
      return
    }

    confirmDialog.loading = true
    try {
      await confirmDialog.onConfirm()
      confirmDialog.show = false
      confirmDialog.onConfirm = null
    } finally {
      confirmDialog.loading = false
    }
  }

  return {
    confirmDialog,
    requestConfirm,
    closeConfirmDialog,
    runConfirmedAction
  }
}
