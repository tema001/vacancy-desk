import { useId, type ReactNode, type SyntheticEvent } from 'react'

interface ModalProps {
  title: ReactNode
  titleExtra?: ReactNode
  closeLabel: string
  onClose: () => void
  children: ReactNode
}

function showDialog(dialog: HTMLDialogElement | null): void {
  if (dialog && !dialog.open) {
    dialog.showModal()
  }
}

export function Modal({ title, titleExtra, closeLabel, onClose, children }: ModalProps) {
  const titleId = useId()

  // The parent unmounts the modal, so cancel the native close to avoid a double close
  function handleCancel(event: SyntheticEvent<HTMLDialogElement>): void {
    event.preventDefault()
    onClose()
  }

  return (
    <dialog
      ref={showDialog}
      className="profile-modal"
      aria-labelledby={titleId}
      onCancel={handleCancel}
    >
      <div className="profile-modal-heading">
        <div className="profile-modal-title">
          <h2 id={titleId}>{title}</h2>
          {titleExtra}
        </div>
        <button
          type="button"
          className="profile-modal-close"
          onClick={onClose}
          aria-label={closeLabel}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  )
}
