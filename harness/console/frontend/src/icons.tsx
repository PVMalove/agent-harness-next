/* Line icons ported from docs/design/web-console-mockups/harness-icons.js: local SVG only. */
import type { ReactElement } from "react";

const PATHS = {
  "home": (
    <><path d="M3.2 10.7 12 3.6l8.8 7.1" /><path d="M5.4 9.4V20a1 1 0 0 0 1 1h11.2a1 1 0 0 0 1-1V9.4" /><path d="M9.6 21v-6.1h4.8V21" /></>
  ),
  "folder": (
    <><path d="M3.2 7.3A1.8 1.8 0 0 1 5 5.5h4l2 2h8a1.8 1.8 0 0 1 1.8 1.8v8.4A1.8 1.8 0 0 1 19 19.5H5a1.8 1.8 0 0 1-1.8-1.8z" /></>
  ),
  "refresh": (
    <><path d="M20 11.2A8 8 0 1 0 17.4 17" /><path d="M20 4.6v6.6h-6.5" /></>
  ),
  "pulse": (
    <><path d="M3 12h3.2l2.1-5.4 4 11 2.2-5.6H21" /></>
  ),
  "harness": (
    <><path d="m12 3.2 7.6 4.4v8.8L12 20.8l-7.6-4.4V7.6z" /><path d="m12 8.1 3.7 2.1v4.2L12 16.5l-3.7-2.1v-4.2z" /></>
  ),
  "orchestration": (
    <><circle cx="6" cy="6.4" r="2.2" /><circle cx="18" cy="6.4" r="2.2" /><circle cx="12" cy="17.6" r="2.2" /><path d="M8.2 6.4h7.6M7.2 8.3l3.6 7.3M16.8 8.3l-3.6 7.3" /></>
  ),
  "reports": (
    <><path d="M6.2 3.4h8.1l3.5 3.5v13.7H6.2z" /><path d="M14.3 3.4v3.6h3.5M9 11h6M9 14.4h6M9 17.8h3.8" /></>
  ),
  "map": (
    <><path d="M9 4.1 3.4 6.2v13.7L9 17.8l6 2.1 5.6-2.1V4.1L15 6.2z" /><path d="M9 4.1v13.7M15 6.2v13.7" /></>
  ),
  "settings": (
    <><path d="M4 7.2h5M13 7.2h7M4 16.8h7M15 16.8h5" /><circle cx="11" cy="7.2" r="2" /><circle cx="13" cy="16.8" r="2" /></>
  ),
  "help": (
    <><circle cx="12" cy="12" r="8.6" /><path d="M9.7 9.1a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1.2 1-1.2 1.8v.4" /><circle cx="12" cy="16.8" r=".55" fill="currentColor" stroke="none" /></>
  ),
  "board": (
    <><rect x="3.2" y="4.2" width="4.2" height="15.6" rx="1" /><rect x="9.9" y="4.2" width="4.2" height="10.2" rx="1" /><rect x="16.6" y="4.2" width="4.2" height="13.2" rx="1" /></>
  ),
  "activity": (
    <><path d="M3 12h3.1l1.7-4.4 3.6 9 2.4-6.2 1.4 3.2H21" /></>
  ),
  "github": (
    <><circle cx="6.2" cy="6.4" r="2.1" /><circle cx="17.8" cy="6.4" r="2.1" /><circle cx="12" cy="18" r="2.1" /><path d="M6.2 8.5v2.1a3 3 0 0 0 3 3h5.6a3 3 0 0 0 3-3V8.5M12 13.6V15.9" /></>
  ),
  "store": (
    <><ellipse cx="12" cy="6.2" rx="7.2" ry="2.7" /><path d="M4.8 6.2v5.6c0 1.5 3.2 2.7 7.2 2.7s7.2-1.2 7.2-2.7V6.2M4.8 11.8v5.6c0 1.5 3.2 2.7 7.2 2.7s7.2-1.2 7.2-2.7v-5.6" /></>
  ),
  "memory": (
    <><rect x="6.4" y="6.4" width="11.2" height="11.2" rx="2" /><path d="M9.5 9.5h5v5h-5zM9.5 3.5v2.9M14.5 3.5v2.9M9.5 17.6v2.9M14.5 17.6v2.9M3.5 9.5h2.9M3.5 14.5h2.9M17.6 9.5h2.9M17.6 14.5h2.9" /></>
  ),
  "chevron": (
    <><path d="m9 5.8 6.2 6.2L9 18.2" /></>
  ),
  "check": (
    <><path d="m5 12.4 4.4 4.4L19 7.2" /></>
  ),
  "x": (
    <><path d="m6.2 6.2 11.6 11.6M17.8 6.2 6.2 17.8" /></>
  ),
  "warning": (
    <><path d="m12 3.8 8.6 15.4H3.4z" /><path d="M12 9.2v4.1" /><circle cx="12" cy="16.5" r=".55" fill="currentColor" stroke="none" /></>
  ),
  "info": (
    <><circle cx="12" cy="12" r="8.6" /><path d="M12 10.7v5.1" /><circle cx="12" cy="8.1" r=".6" fill="currentColor" stroke="none" /></>
  ),
  "clock": (
    <><circle cx="12" cy="12" r="8.6" /><path d="M12 7.4V12l3.1 1.9" /></>
  ),
  "menu": (
    <><path d="M4 6.5h16M4 12h16M4 17.5h16" /></>
  ),
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof PATHS;

const FALLBACK = (
  <><circle cx="12" cy="12" r="8.6" /><path d="M12 8.2v4.4" /><circle cx="12" cy="15.6" r=".55" fill="currentColor" stroke="none" /></>
);

export function Icon({ name, className = "" }: { name: IconName | string; className?: string }) {
  const paths = (PATHS as Record<string, ReactElement>)[name] ?? FALLBACK;
  return (
    <svg
      className={`hi ${className}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.55"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths}
    </svg>
  );
}
