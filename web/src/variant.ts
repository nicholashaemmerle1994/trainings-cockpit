/**
 * Die Variante wird beim Bauen gesetzt: `VITE_APP_VARIANT=preview` baut die
 * Vorschau-Instanz (develop), ohne den Wert entsteht der stabile Stand (main).
 */
export const isPreview = import.meta.env.VITE_APP_VARIANT === "preview";
