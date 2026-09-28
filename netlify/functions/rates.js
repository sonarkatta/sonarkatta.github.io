// Holding mode. The previous external feed uses a different rate basis than
// the owner's requested reference. Do not serve it as a live rate endpoint.
exports.handler = async function () {
  return {
    statusCode: 503,
    headers: {'Cache-Control':'no-store, max-age=0','Content-Type':'application/json; charset=utf-8'},
    body: JSON.stringify({error:'verified_reference_unavailable'})
  };
};
