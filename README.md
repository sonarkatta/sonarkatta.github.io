# Sonar Katta PWA

A mobile-first Marathi rates page. It can be installed from the browser's Add to Home Screen menu once served on HTTPS. All files are static except the small Netlify Function at `netlify/functions/rates.js` that fetches and checks live rates server-side. Netlify is needed for automatic rates; a GitHub Pages upload shows only the verified fallback because the source site does not allow cross-origin browser requests.

## Free hosting with automatic rates: Netlify + GitHub

You need a GitHub account and a Netlify account (sign in to Netlify with GitHub). Setup takes about 10-20 minutes, excluding account sign-up and any Netlify build queue.

1. Unzip this package. In GitHub, create a new **public** repository, for example `sonar-katta-app`. Upload the **contents** of the `sonar-katta-pwa` folder into the repository root (not the enclosing folder). Commit. A public repository makes the baked-in rates and source code visible to anyone; do not put secrets in it.
2. In Netlify, choose **Add new project > Import an existing project > GitHub**. Grant access to that repository and select it.
3. Set the publish directory to `.` (repository root), leave build command empty, and deploy. `netlify.toml` specifies the functions folder. Use the HTTPS `*.netlify.app` URL Netlify gives you. You can change the site name in Netlify settings.
4. Open the site on your phone. Android Chrome: menu > **Add to Home screen** or **Install app**. iPhone Safari: Share > **Add to Home Screen**. Installation options vary by device/browser.
5. Check the timestamp beneath the four prices. "आज तपासलेले" means today's site timestamp passed both server and browser checks. "शेवटचे पडताळलेले" means the saved fallback is showing. The app never claims a stale fetch is today's rate.

No domain purchase is required. Free-plan limits and UI wording can change. Do not promise that the external rate site will always be reachable. This app rechecks on page load, not in the background. For an update while the app is already open, reopen or reload it.

## Manual verified fallback update

In `index.html`, find the block marked `VERIFIED FALLBACK` near the top. Update all fields together: `date` in `YYYY-MM-DD`, `updated` as an ISO 8601 UTC timestamp (e.g., 20:25 IST = `14:55:00.000Z` on the same day), `gold24`, `gold22` and `gold18` per 10 g, `silver999` per 1 kg, and region. Check the figures yourself first. Commit the edit and Netlify redeploys. Until changed, the fallback remains explicitly dated 28 September 2026 at 8:25 PM IST. Never change just the date to make old rates look current.

The server-side scraper requires the source page's main "Last Update" timestamp to be TODAY in India and not in the future. If the site serves an old cache, changes its table, blocks requests or gives an invalid response, the function returns an error and the page displays its dated fallback. The page never displays the source's name to visitors. The source may change its HTML in the future, so inspect the live output before relying on it.
