# Sonar Katta PWA - holding mode

The deployed public app is https://sonarkatta.netlify.app/ . It intentionally displays no prices right now. The owner requires rates that match his All India Bullion reference, but automated access to that source is currently blocked. Do not restore rates from the earlier Bullions feed: it uses a different rate basis.

The static mobile page has an installable manifest, offline service worker and crystal-card design. GitHub repository: https://github.com/tejasdhale/sonar-katta-app . The old serverless rates.js still exists in the repository and may answer direct requests, but the holding page does not call it or display its values. It should not be treated as an approved reference. Once an authorized and reliable source is available, wire its date-checked data to the page and test freshness, weights and all four figures before replacing this notice.
