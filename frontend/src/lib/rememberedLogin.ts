const STORAGE_KEY = 'udaanher_saathi_login_v1';

export interface RememberedLogin {
  name: string;
  pin: string;
}

/** "Remember this phone" (login roadmap item 1): if she regularly uses the
 * same phone, she shouldn't have to enter her code every time. Stored only
 * on this device, cleared on request (a different phone, or logging out). */
export function getRememberedLogin(): RememberedLogin | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.name === 'string' && typeof parsed?.pin === 'string') return parsed;
    return null;
  } catch {
    return null;
  }
}

export function setRememberedLogin(login: RememberedLogin): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(login));
  } catch {
    // private browsing / storage blocked -- she just re-enters next time
  }
}

export function clearRememberedLogin(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing to do
  }
}
