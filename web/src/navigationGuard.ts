/**
 * Ein gemeinsamer Schutz für alle Wege aus einem offenen Entwurf.
 *
 * Router-Zurück, Browser-Zurück und die Hauptnavigation fragen dieselbe
 * Registrierung. Die Entscheidung bleibt beim Entwurf: Er weiß, ob er
 * schmutzig ist, ob ein Schreibvorgang läuft und wie er lokal verworfen wird.
 */
export interface NavigationGuard {
  /** Fachliche Änderungen oder unfertige Feldpuffer vorhanden. */
  isDirty(): boolean;
  /** Ein Schreibvorgang ist gestartet und nicht bestätigt abgeschlossen. */
  isSaving(): boolean;
  /** Nur den lokalen Entwurf verwerfen; ein Remote-Vorgang bleibt bestehen. */
  discard(): void;
}

let current: NavigationGuard | null = null;

export function registerNavigationGuard(guard: NavigationGuard): void {
  current = guard;
}

/** Nur die eigene Registrierung entfernen; eine neuere bleibt stehen. */
export function unregisterNavigationGuard(guard: NavigationGuard): void {
  if (current === guard) current = null;
}

export function activeNavigationGuard(): NavigationGuard | null {
  return current;
}
