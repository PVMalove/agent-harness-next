/* A 34 by 20 px switch (role="switch"): Space and Enter toggle it as on any button. Every flag of
   the redesigned screens is shown this way. */
export function Switch({ checked, onChange, label, disabled = false, id }: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
  id?: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className="ds-sw"
      onClick={() => onChange(!checked)}
    >
      <span className="ds-sw-knob" />
    </button>
  );
}
