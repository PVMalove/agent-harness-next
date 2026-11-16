/* The drawer of the v3 shell: a native modal <dialog> docked to the right edge with a title, a close
   button, a body that scrolls and an optional footer. Escape, the back gesture and a click on the
   backdrop (closedby="any") close it through the dialog's cancel event; a browser without closedBy
   gets the click-outside fallback of modern-web-guidance ui-behaviors/light-dismiss-a-dialog. The
   caller unmounts it to close, so the element that opened it gets the focus back. */
import { useEffect, useId, useRef } from "react";
import type { MouseEvent, ReactNode } from "react";

const LIGHT_DISMISS_NATIVE = typeof HTMLDialogElement !== "undefined" && "closedBy" in HTMLDialogElement.prototype;

/** Whether a click on the dialog element itself landed outside its box, on the backdrop. */
function onBackdrop(event: MouseEvent<HTMLDialogElement>): boolean {
  if (event.target !== event.currentTarget) return false;
  const box = event.currentTarget.getBoundingClientRect();
  return event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
}
import { Icon } from "../icons";

export interface DrawerProps {
  title: ReactNode;
  /** Accessible name of the close button (translated by the caller). */
  closeLabel: string;
  onClose: () => void;
  id?: string;
  footer?: ReactNode;
  children?: ReactNode;
}

export function Drawer({ title, closeLabel, onClose, id, footer, children }: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialog && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    return () => {
      if (opener && opener.isConnected) opener.focus();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      id={id}
      className="ds-drawer"
      aria-labelledby={titleId}
      {...({ closedby: "any" } as object)}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (!LIGHT_DISMISS_NATIVE && onBackdrop(event)) onClose();
      }}
    >
      <div className="ds-drawer-head">
        <h2 className="ds-drawer-title" id={titleId}>
          {title}
        </h2>
        <button className="ds-btn ds-btn-icon" type="button" aria-label={closeLabel} onClick={onClose}>
          <Icon name="x" className="ds-ic" />
        </button>
      </div>
      <div className="ds-drawer-body">{children}</div>
      {footer ? <div className="ds-drawer-foot">{footer}</div> : null}
    </dialog>
  );
}
