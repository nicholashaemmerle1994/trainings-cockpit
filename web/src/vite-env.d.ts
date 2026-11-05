/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_VARIANT?: "preview" | "stable";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
