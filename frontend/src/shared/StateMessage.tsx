interface StateMessageProps {
  kind: 'loading' | 'error' | 'empty'
  title: string
  text: string
  action?: { label: string; onClick: () => void }
}

export function StateMessage({ kind, title, text, action }: StateMessageProps) {
  const className = kind === 'error' ? 'state-message error-state' : 'state-message'
  const role = kind === 'loading' ? 'status' : kind === 'error' ? 'alert' : undefined

  return (
    <div className={className} role={role}>
      {kind === 'loading' ? (
        <span className="spinner large-spinner" aria-hidden="true" />
      ) : (
        <span
          className={kind === 'error' ? 'state-icon' : 'state-icon empty-icon'}
          aria-hidden="true"
        >
          {kind === 'error' ? '!' : '0'}
        </span>
      )}
      <strong>{title}</strong>
      <span>{text}</span>
      {action ? (
        <button type="button" className="secondary-button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </div>
  )
}
