export const config = {
  base: (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, ''),
  domain: import.meta.env.VITE_COGNITO_DOMAIN || '', client: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
  redirect: import.meta.env.VITE_COGNITO_REDIRECT_URI || window.location.origin + '/',
};
let accessToken = '';
let expiresAt = 0;
export function signedIn() { return !!accessToken && Date.now() < expiresAt; }
export function signOut() { accessToken = ''; expiresAt = 0; }
const messages: Record<number,string> = {401:'Your session has expired. Sign in again.',403:'Your account does not have permission for this action.',404:'This record is unavailable or belongs to another account.',422:'Check your locations, mode and departure time.',429:'Request limit reached. Wait before trying again.',503:'This service is not configured or temporarily unavailable.'};
const routingMessages:Record<string,string> = {
  health_connect_phone_unreachable:'Cannot reach your phone. Keep its server running and reconnect both devices to the same Wi-Fi.',
  health_connect_timeout:'The phone took too long to respond. Unlock it, check the server and try again.',
  health_connect_phone_permission_denied:'The phone rejected access. Check its local HTTP token and Health Connect permissions.',
  health_connect_phone_read_failed:'The phone could not read Health Connect. Check the selected data types and permissions.',
  health_connect_not_configured:'Configure HEALTH_CONNECT_BASE_URL in the backend .env and restart the backend.',
  health_connect_owner_not_configured:'Configure the Health Connect owner in the backend before reading personal data.',
  health_connect_owner_mismatch:'This phone bridge belongs to a different account.',
  health_connect_pairing_expired:'Your local pairing key expired. Generate a new key with scripts/health_connect.py and restart the backend.',
  health_connect_local_access_only:'Local pairing works only through the backend on this laptop’s localhost address.',
  health_connect_consent_required:'Allow this session to read Health Connect before fetching records.',
  health_connect_invalid_response:'The phone returned an invalid response. Check its server version and try again.',
  health_connect_schema_changed:'The phone response format has changed. Update the bridge adapter before reading it.',
  health_connect_payload_too_large:'The phone returned too much data. Try a shorter data window.',
  health_connect_invalid_timezone:'Your time zone is not supported. Check the backend time-zone data installation.',
  health_connect_date_outside_window:'Choose a date within the last seven days.',
  health_connect_request_in_progress:'A phone read is already running. Wait for it to finish.',
  health_connect_phone_rate_limited:'The phone is limiting requests. Wait before refreshing.',
  guest_routes_disabled:'Guest routing is not enabled on this backend. Configure ENABLE_GUEST_ROUTES or sign in.',
  guest_routes_require_request_only_google:'Guest routing requires ROUTING_PROVIDER=google on the backend. Private journey storage remains protected.',
  cycling_request_rejected:'The bicycle route request was rejected. Try nearby endpoints or reduce alternatives.',
  google_routes_key_missing:'The map is connected, but routing needs GOOGLE_ROUTES_API_KEY in the backend .env. Use a separate server key.',
  google_access_or_billing_unavailable:'Google routing access is unavailable. Check the server key, Routes/Places APIs and Google billing.',
  google_no_route_for_selected_mode:'Google returned no route for this travel mode. Try different endpoints; no driving route was substituted.',
  google_route_request_rejected:'Google rejected this route request. Check your endpoints, travel mode and departure time.',
  cycling_provider_not_configured:'Cycle needs CYCLING_PROVIDER=openrouteservice and its server key. Google does not list bicycle routing for India.',
  cycling_key_missing:'Add OPENROUTESERVICE_API_KEY to the backend .env to connect cycling routes.',
  cycling_no_route:'The cycling provider could not find a bicycle route between these points. Try nearby accessible points.',
  cycling_access_unavailable:'The cycling provider rejected its key or plan. Check the server configuration.',
  geocoding_no_match:'The place could not be found. Choose the location on the map or enter a more specific address.',
  geocoding_ambiguous_use_coordinates:'Several places matched that name. Choose the exact point on the map.',
  outside_supported_delhi_area:'The selected legacy routing provider is limited to Delhi. Select the Google provider for other locations.',
  route_outside_demo_limits:'Choose a shorter route: comparisons support up to 100 km and six hours of travel.',
};
export async function request<T>(path: string, body?: unknown, authenticated = true): Promise<T> {
  if (authenticated && !signedIn()) throw new Error('Sign in with Cognito to use live services. Historical preview remains available.');
  return send<T>(path,body,authenticated?accessToken:undefined,authenticated);
}
// A local pairing key authorizes only this small, read-only API. It never signs in to other services.
export async function requestHealthConnect<T>(path:string,localKey='',signal?:AbortSignal):Promise<T>{
  if(!/^\/wearables\/health-connect\/(status|data|summary)(\?|$)/.test(path))throw new Error('Invalid Health Connect endpoint.');
  if(!localKey&&!signedIn())throw new Error('Enter the local pairing key, or sign in with Cognito.');
  return send<T>(path,undefined,localKey||accessToken,!localKey,signal);
}
async function send<T>(path:string,body:unknown,token:string|undefined,cognito:boolean,signal?:AbortSignal):Promise<T>{
  const url = new URL(config.base);
  if (!['http:','https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Check VITE_API_BASE_URL: use an HTTP/HTTPS backend address without credentials or query parameters.');
  if (url.protocol !== 'https:' && !['localhost','127.0.0.1'].includes(url.hostname)) throw new Error('The API must use HTTPS.');
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 20000);
  const abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
  try {
    const response = await fetch(config.base + '/api/v1' + path, { method: body === undefined ? 'GET':'POST', cache:'no-store', credentials:'omit', signal:controller.signal,
      headers: { ...(body === undefined ? {} : {'Content-Type':'application/json'}), ...(token ? {Authorization:`Bearer ${token}`} : {}) }, ...(body === undefined ? {} : {body:JSON.stringify(body)}) });
    if (!response.ok) {
      if(response.status===401&&cognito) signOut();
      // Only allowlisted codes become UI messages; never render provider bodies or echoed secrets.
      let code=''; try {const body=await response.json(); code=typeof body?.error?.code==='string'?body.error.code:'';} catch { /* Non-JSON failures use the HTTP status. */ }
      throw new Error(routingMessages[code] || messages[response.status] || 'The request failed. Try again later.');
    }
    return await response.json();
  } catch (error) { if (error instanceof TypeError || (error instanceof DOMException && error.name==='AbortError')) throw new Error('Cannot reach the backend. Check its address, connection and CORS configuration.'); throw error; }
  finally { clearTimeout(timer);signal?.removeEventListener('abort',abort); }
}
const encode = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
export async function signIn() {
  if(!config.domain || !config.client) throw new Error('Cognito is not configured yet. Set the public Cognito domain and client ID in frontend/.env.local.');
  const domain = new URL(config.domain);
  if(domain.protocol !== 'https:') throw new Error('Cognito must use HTTPS.');
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32))), state = encode(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem('ecoroute-pkce', JSON.stringify({verifier,state,created:Date.now()}));
  const challenge = encode(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
  const url = new URL('/oauth2/authorize',domain);
  url.search = new URLSearchParams({response_type:'code',client_id:config.client,redirect_uri:config.redirect,scope:'openid ecoroute/read ecoroute/write',state,code_challenge:challenge,code_challenge_method:'S256'}).toString();
  window.location.assign(url);
}
export async function finishSignIn() {
  const query = new URLSearchParams(location.search); if(!query.has('code') && !query.has('error')) return false;
  const saved = sessionStorage.getItem('ecoroute-pkce'); sessionStorage.removeItem('ecoroute-pkce');
  history.replaceState({},'',location.pathname);
  if(query.has('error') || !saved) throw new Error('Sign-in was cancelled or expired. Try again.');
  const flow = JSON.parse(saved);
  if(query.get('state')!==flow.state || Date.now()-flow.created>600000) throw new Error('Sign-in verification failed. Start again.');
  const response = await fetch(new URL('/oauth2/token',config.domain), {method:'POST', credentials:'omit', headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:config.client,redirect_uri:config.redirect,code:query.get('code')!,code_verifier:flow.verifier})});
  if(!response.ok) throw new Error('Cognito could not finish sign-in. Check the callback configuration.');
  const value = await response.json();
  if(typeof value.access_token!=='string' || !(value.expires_in>0)) throw new Error('Invalid sign-in response.');
  accessToken=value.access_token; expiresAt=Date.now()+value.expires_in*1000; // Memory only. Reload requires login.
  return true;
}
