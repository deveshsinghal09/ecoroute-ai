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
export async function request<T>(path: string, body?: unknown, authenticated = true): Promise<T> {
  if (authenticated && !signedIn()) throw new Error('Sign in with Cognito to use live services. Historical preview remains available.');
  const url = new URL(config.base);
  if (url.protocol !== 'https:' && !['localhost','127.0.0.1'].includes(url.hostname)) throw new Error('The API must use HTTPS.');
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(config.base + '/api/v1' + path, { method: body === undefined ? 'GET':'POST', cache:'no-store', credentials:'omit', signal:controller.signal,
      headers: { ...(body === undefined ? {} : {'Content-Type':'application/json'}), ...(authenticated ? {Authorization:`Bearer ${accessToken}`} : {}) }, ...(body === undefined ? {} : {body:JSON.stringify(body)}) });
    if (!response.ok) { if(response.status===401) signOut(); throw new Error(messages[response.status] || 'The request failed. Try again later.'); }
    return await response.json();
  } catch (error) { if (error instanceof TypeError || (error instanceof DOMException && error.name==='AbortError')) throw new Error('Cannot reach the backend. Check its address, connection and CORS configuration.'); throw error; }
  finally { clearTimeout(timer); }
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
