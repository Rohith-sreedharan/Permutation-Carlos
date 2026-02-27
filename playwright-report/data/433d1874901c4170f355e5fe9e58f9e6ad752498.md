# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e4]: "[plugin:vite:import-analysis] Failed to resolve import \"./App\" from \"index.tsx\". Does the file exist?"
  - generic [ref=e5]: /root/permu/index.tsx:4:16
  - generic [ref=e6]: 2 | import React from "react"; 3 | import ReactDOM from "react-dom/client"; 4 | import App from "./App"; | ^ 5 | import "./src/index.css"; 6 | const rootElement = document.getElementById("root");
  - generic [ref=e7]: at TransformPluginContext._formatLog (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:42528:41) at TransformPluginContext.error (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:42525:16) at normalizeUrl (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:40504:23) at process.processTicksAndRejections (node:internal/process/task_queues:95:5) at async file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:40623:37 at async Promise.all (index 3) at async TransformPluginContext.transform (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:40550:7) at async EnvironmentPluginContainer.transform (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:42323:18) at async loadAndTransform (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:35739:27) at async viteTransformMiddleware (file:///root/permu/node_modules/vite/dist/node/chunks/dep-D4NMHUTW.js:37254:24
  - generic [ref=e8]:
    - text: Click outside, press Esc key, or fix the code to dismiss.
    - text: You can also disable this overlay by setting
    - code [ref=e9]: server.hmr.overlay
    - text: to
    - code [ref=e10]: "false"
    - text: in
    - code [ref=e11]: vite.config.ts
    - text: .
```