const STORAGE_KEY = "voice_cloning_consent_v1";

export function hasConsent() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "granted";
  } catch {
    return false;
  }
}

export function grantConsent() {
  try { localStorage.setItem(STORAGE_KEY, "granted"); } catch { /* noop */ }
}

export function clearConsent() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
}
