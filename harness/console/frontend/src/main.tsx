import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { LanguageProvider } from "./i18n";
import { applyTheme, readTheme } from "./theme";
import "./styles/fonts.css";
import "./styles/app.css";
import "./styles/ds-tokens.css";
import "./styles/ds-shell.css";
import "./styles/ds-components.css";
import "./styles/ds-screens.css";

// Before the first render: a pinned theme replaces the system scheme from the start.
applyTheme(readTheme());

const root = document.getElementById("root");
if (!root) throw new Error("#root is missing");
createRoot(root).render(
  <StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </StrictMode>,
);
