interface RefreshButtonProps {
  onClick: () => void
  disabled: boolean
}

export function RefreshButton({ onClick, disabled }: RefreshButtonProps) {
  return (
    <button
      type="button"
      className="secondary-button refresh-button"
      onClick={onClick}
      disabled={disabled}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M20 11a8.1 8.1 0 0 0-14.9-4M4 4v4h4m-4 5a8.1 8.1 0 0 0 14.9 4M20 20v-4h-4" />
      </svg>
      Refresh
    </button>
  )
}
