// SPDX-FileCopyrightText: 2026 Ernest Borysenko
// SPDX-License-Identifier: Apache-2.0

import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_DEV_PORT || 5173),
    },
  };
});
