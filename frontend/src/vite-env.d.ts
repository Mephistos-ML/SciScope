/// <reference types="vite/client" />
// SPDX-FileCopyrightText: 2026 Ernest Borysenko
// SPDX-License-Identifier: Apache-2.0

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_API_TIMEOUT_MS?: string;
  readonly VITE_TURNSTILE_SITE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.svg" {
  const src: string;
  export default src;
}
