import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css"; // doit contenir les directives Tailwind (@tailwind base/components/utilities)

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
