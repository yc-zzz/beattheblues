// Backend base URLs, set per environment instead of hard-coded in each page.
//
// Create React App copies REACT_APP_* variables into the JavaScript bundle at
// BUILD time. After changing them in Vercel (Settings > Environment
// Variables) you must redeploy for the site to pick them up.
//
// Each falls back to the original Render URL, so the site behaves exactly as
// before until the variables are set.
const withoutTrailingSlash = (url: string) => url.replace(/\/+$/, '');

// my-backend (Node/Express): accounts, playlists, random song
export const API_URL = withoutTrailingSlash(
  process.env.REACT_APP_API_URL || 'https://beattheblues.onrender.com'
);

// master_app.py (Flask): search, recommendations, personality test
export const RECO_API_URL = withoutTrailingSlash(
  process.env.REACT_APP_RECO_API_URL || 'https://beattheblues-reco.onrender.com'
);
