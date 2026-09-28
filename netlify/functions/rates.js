// The source never appears in the public app UI. The server-side function
// reads it because browsers cannot fetch the site across origins (no CORS).
const SOURCE = 'https://bullions.co.in/location/mumbai/';
const IST = 'Asia/Kolkata';
const month = {jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};
const headers = {'Cache-Control':'no-store, max-age=0','Content-Type':'application/json; charset=utf-8','X-Content-Type-Options':'nosniff'};
const failure = () => ({statusCode:503,headers,body:JSON.stringify({error:'live_rates_unavailable'})});
function istDate(date) { return new Intl.DateTimeFormat('en-CA',{timeZone:IST,year:'numeric',month:'2-digit',day:'2-digit'}).format(date); }
function parsePage(html, now = new Date()) {
  // Match the main rates section's Last Update, never a timestamp in another table.
  const head = html.match(/Gold Rate Today in Mumbai[\s\S]{0,4000}?Last Update[\s\S]{0,300}?<strong[^>]*>\s*(?:[A-Za-z]+,\s*)?(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{1,2}):(\d{2})(?:\s*(AM|PM))?/i);
  if (!head) throw Error('No source timestamp');
  const [,d,m,y,h,min,period] = head;
  if (!(m.toLowerCase() in month)) throw Error('Unknown source month');
  let hour = +h;
  // The source sometimes writes "20:15 PM"; 24-hour time wins.
  if (hour < 1 || hour > 23 || +min > 59) {
    if (!(hour === 0 && !period)) throw Error('Invalid source time');
  }
  if (period && hour <= 12) hour = period.toUpperCase() === 'PM' ? hour % 12 + 12 : hour % 12;
  const updated = new Date(Date.UTC(+y, month[m.toLowerCase()], +d, hour, +min) - 330*60000);
  if (isNaN(updated.valueOf())) throw Error('Invalid timestamp');
  const sourceDay = `${y}-${String(month[m.toLowerCase()]+1).padStart(2,'0')}-${String(+d).padStart(2,'0')}`;
  if (istDate(updated) !== sourceDay || istDate(now) !== sourceDay || updated.getTime() > now.getTime() + 5*60000) throw Error('Stale or future source timestamp');
  // Keep each price tied to its own table row and the requested weight column.
  function price(label, column) {
    const row = html.match(new RegExp('<tr[^>]*>\\s*<td[^>]*>\\s*'+label+'\\b[\\s\\S]*?<\\/tr>','i'));
    if (!row) throw Error('Missing price row');
    const cells = [...row[0].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(x=>x[1].replace(/<[^>]*>/g,'').trim());
    const value = cells[column];
    if (!/^\d{1,3}(?:,\d{3})+$/.test(value) || Number(value.replace(/,/g,'')) < 1000) throw Error('Invalid price');
    return '₹'+value;
  }
  return {date:sourceDay, updated:updated.toISOString(), gold24:price('Gold 24 Karat',2),gold22:price('Gold 22 Karat',2),gold18:price('Gold 18 Karat',2),silver999:price('Silver 999 Fine',4)};
}
exports.handler = async function() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(), 8000);
    let response;
    try { response = await fetch(SOURCE, {signal:controller.signal,headers:{'Accept':'text/html','Cache-Control':'no-cache'}}); }
    finally { clearTimeout(timeout); }
    if (!response.ok) return failure();
    const html = await response.text();
    const rates = parsePage(html);
    return {statusCode:200,headers,body:JSON.stringify(rates)};
  } catch (_) { return failure(); }
};
exports.parsePage = parsePage;
