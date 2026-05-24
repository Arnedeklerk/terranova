import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initBridge } from "./bridge";
import "./styles/global.css";

async function boot() {
  await initBridge();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

boot().catch((err) => {
  // Render a minimal error surface — never blank screen.
  document.getElementById("root")!.innerHTML =
    `<pre style="padding:24px;color:#E5484D;font-family:monospace">${String(err)}</pre>`;
});
