/* A 40 by 24 px switch (role="switch", a 24 px target, WCAG 2.5.8): Space and Enter toggle it as on
   any button, and the knob carries a check mark when on, so the state is a shape and not only a
   colour. A disabled switch stays in the Tab order (aria-disabled) and `describedBy` names the
   element that says why it cannot change (modern-web-guidance accessibility/accessibility). Every
   flag of the redesigned screens is shown this way. */
export function Switch({ checked, onChange, label, disabled = false, describedBy, id }: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
  /** The id of the visible reason a disabled switch cannot change. */
  describedBy?: string;
  id?: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-disabled={disabled || undefined}
      aria-describedby={disabled ? describedBy : undefined}
      className="ds-sw"
      onClick={() => {
        if (!disabled) onChange(!checked);
      }}
    >
      <span className="ds-sw-knob" />
    </button>
  );
}
