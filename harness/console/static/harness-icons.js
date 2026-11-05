/* Apple/SF-Symbols-inspired line icon set for the Harness web mockups.
   Drawn locally as SVG: no external assets, no icon font, no brand trademarks. */
(() => {
  "use strict";

  const paths = {
    home: '<path d="M3.2 10.7 12 3.6l8.8 7.1"/><path d="M5.4 9.4V20a1 1 0 0 0 1 1h11.2a1 1 0 0 0 1-1V9.4"/><path d="M9.6 21v-6.1h4.8V21"/>',
    folder: '<path d="M3.2 7.3A1.8 1.8 0 0 1 5 5.5h4l2 2h8a1.8 1.8 0 0 1 1.8 1.8v8.4A1.8 1.8 0 0 1 19 19.5H5a1.8 1.8 0 0 1-1.8-1.8z"/>',
    refresh: '<path d="M20 11.2A8 8 0 1 0 17.4 17"/><path d="M20 4.6v6.6h-6.5"/>',
    pulse: '<path d="M3 12h3.2l2.1-5.4 4 11 2.2-5.6H21"/>',
    harness: '<path d="m12 3.2 7.6 4.4v8.8L12 20.8l-7.6-4.4V7.6z"/><path d="m12 8.1 3.7 2.1v4.2L12 16.5l-3.7-2.1v-4.2z"/>',
    orchestration: '<circle cx="6" cy="6.4" r="2.2"/><circle cx="18" cy="6.4" r="2.2"/><circle cx="12" cy="17.6" r="2.2"/><path d="M8.2 6.4h7.6M7.2 8.3l3.6 7.3M16.8 8.3l-3.6 7.3"/>',
    reports: '<path d="M6.2 3.4h8.1l3.5 3.5v13.7H6.2z"/><path d="M14.3 3.4v3.6h3.5M9 11h6M9 14.4h6M9 17.8h3.8"/>',
    map: '<path d="M9 4.1 3.4 6.2v13.7L9 17.8l6 2.1 5.6-2.1V4.1L15 6.2z"/><path d="M9 4.1v13.7M15 6.2v13.7"/>',
    settings: '<path d="M4 7.2h5M13 7.2h7M4 16.8h7M15 16.8h5"/><circle cx="11" cy="7.2" r="2"/><circle cx="13" cy="16.8" r="2"/>',
    help: '<circle cx="12" cy="12" r="8.6"/><path d="M9.7 9.1a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1.2 1-1.2 1.8v.4"/><circle cx="12" cy="16.8" r=".55" fill="currentColor" stroke="none"/>',
    board: '<rect x="3.2" y="4.2" width="4.2" height="15.6" rx="1"/><rect x="9.9" y="4.2" width="4.2" height="10.2" rx="1"/><rect x="16.6" y="4.2" width="4.2" height="13.2" rx="1"/>',
    activity: '<path d="M3 12h3.1l1.7-4.4 3.6 9 2.4-6.2 1.4 3.2H21"/>',
    architect: '<circle cx="12" cy="12" r="8.6"/><path d="m15.8 8.2-2.1 5.5-5.5 2.1 2.1-5.5z"/>',
    developer: '<path d="M8.2 8 4.3 12l3.9 4M15.8 8l3.9 4-3.9 4M13.8 5.8l-3.6 12.4"/>',
    review: '<path d="M2.8 12s3.4-6.2 9.2-6.2S21.2 12 21.2 12s-3.4 6.2-9.2 6.2S2.8 12 2.8 12Z"/><circle cx="12" cy="12" r="2.5"/>',
    qa: '<path d="M9 3.4h6M10.2 3.4v6.1L6 17.4a2 2 0 0 0 1.8 3h8.4a2 2 0 0 0 1.8-3l-4.2-7.9V3.4"/><path d="M8.4 14.8h7.2"/>',
    github: '<circle cx="6.2" cy="6.4" r="2.1"/><circle cx="17.8" cy="6.4" r="2.1"/><circle cx="12" cy="18" r="2.1"/><path d="M6.2 8.5v2.1a3 3 0 0 0 3 3h5.6a3 3 0 0 0 3-3V8.5M12 13.6V15.9"/>',
    play: '<circle cx="12" cy="12" r="8.6"/><path d="m10.2 8.7 4.7 3.3-4.7 3.3z"/>',
    blocked: '<path d="M8.2 3.4h7.6l4.8 4.8v7.6l-4.8 4.8H8.2l-4.8-4.8V8.2z"/><path d="m9 9 6 6M15 9l-6 6"/>',
    awaiting: '<circle cx="12" cy="12" r="8.6"/><path d="M9.8 9v6M14.2 9v6"/>',
    completed: '<circle cx="12" cy="12" r="8.6"/><path d="m8.2 12.2 2.6 2.6 5.1-5.3"/>',
    health: '<path d="M12 20.1S3.6 15.2 3.6 9.2a4.5 4.5 0 0 1 8.4-2.1A4.5 4.5 0 0 1 20.4 9.2c0 6-8.4 10.9-8.4 10.9Z"/><path d="M6.8 11.6h2.6l1.3-2.3 2 4.5 1.3-2.2h3.2"/>',
    version: '<circle cx="12" cy="12" r="8.6"/><path d="M12 16.4V7.8M8.8 11l3.2-3.2L15.2 11"/>',
    store: '<ellipse cx="12" cy="6.2" rx="7.2" ry="2.7"/><path d="M4.8 6.2v5.6c0 1.5 3.2 2.7 7.2 2.7s7.2-1.2 7.2-2.7V6.2M4.8 11.8v5.6c0 1.5 3.2 2.7 7.2 2.7s7.2-1.2 7.2-2.7v-5.6"/>',
    skills: '<rect x="4" y="4.2" width="16" height="4.6" rx="1.4"/><rect x="4" y="10" width="16" height="4.6" rx="1.4"/><rect x="4" y="15.8" width="16" height="4" rx="1.4"/>',
    runtime: '<rect x="7.1" y="7.1" width="9.8" height="9.8" rx="2"/><path d="M9.7 3.3v3.8M14.3 3.3v3.8M9.7 16.9v3.8M14.3 16.9v3.8M3.3 9.7h3.8M3.3 14.3h3.8M16.9 9.7h3.8M16.9 14.3h3.8"/>',
    memory: '<rect x="6.4" y="6.4" width="11.2" height="11.2" rx="2"/><path d="M9.5 9.5h5v5h-5zM9.5 3.5v2.9M14.5 3.5v2.9M9.5 17.6v2.9M14.5 17.6v2.9M3.5 9.5h2.9M3.5 14.5h2.9M17.6 9.5h2.9M17.6 14.5h2.9"/>',
    update: '<path d="M20 8.2A8.3 8.3 0 0 0 5.3 6.1L3.4 8.4M3.4 8.4V4.1M3.4 8.4h4.3M4 15.8a8.3 8.3 0 0 0 14.7 2.1l1.9-2.3M20.6 15.6v4.3M20.6 15.6h-4.3"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.4"/><path d="m15.6 15.6 4.1 4.1"/>',
    command: '<path d="M9 9h6v6H9z"/><path d="M9 9H7.5a2.5 2.5 0 1 1 2.5-2.5V9M15 9h1.5a2.5 2.5 0 1 0-2.5-2.5V9M9 15H7.5a2.5 2.5 0 1 0 2.5 2.5V15M15 15h1.5a2.5 2.5 0 1 1-2.5 2.5V15"/>',
    external: '<path d="M14 4.8h5.2V10M19.2 4.8l-7.1 7.1"/><path d="M18.4 14.2v4.1a1.5 1.5 0 0 1-1.5 1.5H5.7a1.5 1.5 0 0 1-1.5-1.5V7.1a1.5 1.5 0 0 1 1.5-1.5h4.1"/>',
    chevron: '<path d="m9 5.8 6.2 6.2L9 18.2"/>',
    check: '<path d="m5 12.4 4.4 4.4L19 7.2"/>',
    x: '<path d="m6.2 6.2 11.6 11.6M17.8 6.2 6.2 17.8"/>',
    warning: '<path d="m12 3.8 8.6 15.4H3.4z"/><path d="M12 9.2v4.1"/><circle cx="12" cy="16.5" r=".55" fill="currentColor" stroke="none"/>',
    info: '<circle cx="12" cy="12" r="8.6"/><path d="M12 10.7v5.1"/><circle cx="12" cy="8.1" r=".6" fill="currentColor" stroke="none"/>',
    lock: '<rect x="5.2" y="10.2" width="13.6" height="9.6" rx="2"/><path d="M8.3 10.2V7.8a3.7 3.7 0 0 1 7.4 0v2.4"/>',
    clock: '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.4V12l3.1 1.9"/>',
    terminal: '<rect x="3.4" y="4.8" width="17.2" height="14.4" rx="2"/><path d="m7.2 9.2 2.6 2.5-2.6 2.5M12.4 14.4h4.2"/>',
    branch: '<circle cx="6.2" cy="6.4" r="2.1"/><circle cx="6.2" cy="17.6" r="2.1"/><circle cx="17.8" cy="8.1" r="2.1"/><path d="M6.2 8.5v7M8.3 6.4h4.9a4.6 4.6 0 0 1 4.6 4.6v4.5"/>',
    shield: '<path d="M12 3.4 19 6v5.6c0 4.3-2.7 7.1-7 9-4.3-1.9-7-4.7-7-9V6z"/><path d="m8.6 11.8 2.3 2.3 4.5-4.6"/>',
    container: '<path d="M4 8.2 12 4l8 4.2v7.6L12 20l-8-4.2z"/><path d="M4 8.2 12 12l8-3.8M12 12v8"/>',
    tokens: '<path d="M12 3.6 20 8v8l-8 4.4L4 16V8z"/><path d="M8.2 10.2 12 12l3.8-1.8M12 12v4.2"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    door: '<path d="M4.2 20.4h15.6M6.5 20.4V5.2a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v15.2"/><path d="M14.3 12.2h.01"/>',
    'github-mark': '<path fill="currentColor" stroke="none" d="M12 .7C5.7.7.6 5.8.6 12.1c0 5 3.2 9.3 7.7 10.8.6.1.8-.2.8-.5v-1.8c-3.1.7-3.8-1.3-3.8-1.3-.5-1.3-1.2-1.6-1.2-1.6-1-.7.1-.7.1-.7 1.1.1 1.7 1.1 1.7 1.1 1 1.7 2.6 1.2 3.2.9.1-.7.4-1.2.7-1.5-2.5-.3-5.1-1.2-5.1-5.5 0-1.2.4-2.2 1.1-3-.1-.3-.5-1.4.1-2.9 0 0 .9-.3 3 1.1a10.4 10.4 0 0 1 5.4 0c2.1-1.4 3-1.1 3-1.1.6 1.5.2 2.6.1 2.9.7.8 1.1 1.8 1.1 3 0 4.3-2.6 5.2-5.1 5.5.4.4.8 1.1.8 2.2v3.3c0 .3.2.6.8.5a11.4 11.4 0 0 0 7.8-10.8C23.4 5.8 18.3.7 12 .7Z"/>',
    'gitlab-mark': '<path fill="currentColor" stroke="none" d="M12 21.5 2.5 14.5l1.8-5.8L6.4 2.2 9.4 9.6h5.2l3-7.4 2.1 6.5 1.8 5.8z"/>',
    search: '<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>',
    download: '<path d="M12 3v11"/><path d="m7 10 5 5 5-5"/><path d="M4 19h16"/>',
    pr: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/><path d="M6 7v10M18 17V9a4 4 0 0 0-4-4h-3"/>',
    menu: '<path d="M4 6.5h16M4 12h16M4 17.5h16"/>',
    grid: '<rect x="4" y="4" width="6.4" height="6.4" rx="1.2"/><rect x="13.6" y="4" width="6.4" height="6.4" rx="1.2"/><rect x="4" y="13.6" width="6.4" height="6.4" rx="1.2"/><rect x="13.6" y="13.6" width="6.4" height="6.4" rx="1.2"/>'
  };

  const fallback = '<circle cx="12" cy="12" r="8.6"/><path d="M12 8.2v4.4"/><circle cx="12" cy="15.6" r=".55" fill="currentColor" stroke="none"/>';

  const get = (name, className = "") =>
    `<svg class="hi ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name] || fallback}</svg>`;

  window.HarnessIcons = { get, paths };
})();

// Only fixed, package-owned icon paths are parsed; project data never enters SVG markup.
document.querySelectorAll('[data-icon]').forEach(element => {
  const svg = new DOMParser().parseFromString(window.HarnessIcons.get(element.dataset.icon), 'image/svg+xml').documentElement;
  element.replaceChildren(document.importNode(svg, true));
});
