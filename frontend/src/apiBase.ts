// Falls back to the deployed Render backend when VITE_API_BASE_URL isn't
// set at build time. Cloudflare Pages' dashboard build config doesn't
// currently set it, and without this fallback every API call silently goes
// to the frontend's own origin instead — Cloudflare Pages' SPA fallback
// returns index.html (200 OK) for any unmatched path, so the failure never
// surfaces as a network error. It just looks like an empty graph and a
// chat that mysteriously never answers.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://openrag-avea.onrender.com'
