/** Content-Security-Policy for the SPA.
 *
 * The app is served by Vite in development and by a static host in production,
 * so the policy is attached here rather than by the API. Development needs the
 * HMR client (inline bootstrap script + a websocket back to the dev server);
 * production does not, and gets the strict policy.
 *
 * `accounts.google.com` is required by Google Identity Services, which loads its
 * script from there and renders the account chooser in an iframe.
 */

const GOOGLE = "https://accounts.google.com";
const FONTS_CSS = "https://fonts.googleapis.com";
const FONTS_FILES = "https://fonts.gstatic.com";

export function buildCsp(apiOrigin: string, { dev = false }: { dev?: boolean } = {}): string {
  const connect = ["'self'", apiOrigin, GOOGLE].filter(Boolean);
  if (dev) {
    // Vite pushes updates over ws:// from the dev server itself.
    connect.push("ws:", "wss:");
  }

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // Vite's dev bootstrap is an inline module; the production bundle is not.
    "script-src": dev ? ["'self'", "'unsafe-inline'", GOOGLE] : ["'self'", GOOGLE],
    // Styled-in-JS and Google Fonts both need inline styles.
    "style-src": ["'self'", "'unsafe-inline'", FONTS_CSS],
    "font-src": ["'self'", FONTS_FILES],
    "img-src": ["'self'", "data:"],
    "connect-src": connect,
    "frame-src": [GOOGLE],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };

  return Object.entries(directives)
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}
