import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

describe('API connection and guest authorization', () => {
  let api: typeof import('./api');
  beforeEach(async () => {
    vi.stubGlobal('window', {location:{origin:'http://127.0.0.1:5173'}});
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true,json:async()=>({routes:[]})}));
    api = await import('./api');
    api.config.base = 'http://127.0.0.1:8000';
    api.signOut();
  });
  afterEach(() => {api.config.base='http://127.0.0.1:8000';vi.unstubAllGlobals();});

  it.each(['shttp://127.0.0.1:8000','ftp://127.0.0.1:8000',
    'http://user:password@127.0.0.1:8000','http://127.0.0.1:8000?token=example',
    'http://127.0.0.1:8000#example'])('rejects unsafe or malformed base %s before networking', async base => {
    api.config.base=base;
    await expect(api.request('/routes/preview',{},false)).rejects.toThrow('Check VITE_API_BASE_URL');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('requires HTTPS outside local development', async () => {
    api.config.base='http://example.com';
    await expect(api.request('/routes/preview',{},false)).rejects.toThrow('HTTPS');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('allows the explicit guest comparison without credentials', async () => {
    await api.request('/routes/preview',{consent_to_store:false},false);
    expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/routes/preview',expect.objectContaining({
      method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},
    }));
  });
  it('keeps private wearable reads protected', async () => {
    await expect(api.request('/wearables/latest')).rejects.toThrow('Sign in with Cognito');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('requires authentication for phone reads and confines the local key to bridge endpoints', async () => {
    await expect(api.requestHealthConnect('/wearables/health-connect/summary')).rejects.toThrow('pairing key');
    await expect(api.requestHealthConnect('/wearables/latest','SYNTHETIC_PAIR_KEY')).rejects.toThrow('Invalid Health Connect');
    expect(fetch).not.toHaveBeenCalled();
    await api.requestHealthConnect('/wearables/health-connect/summary?consent=true','SYNTHETIC_PAIR_KEY');
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/health-connect/summary?consent=true'),expect.objectContaining({method:'GET',cache:'no-store',credentials:'omit',headers:{Authorization:'Bearer SYNTHETIC_PAIR_KEY'}}));
    expect(api.signedIn()).toBe(false);
    await expect(api.request('/wearables/latest')).rejects.toThrow('Sign in with Cognito');
  });
  it('shows only safe bridge errors, never provider text or credentials', async () => {
    vi.mocked(fetch).mockResolvedValue({ok:false,status:504,json:async()=>({error:{code:'health_connect_timeout',detail:'PRIVATE_MARKER'}})} as Response);
    await expect(api.requestHealthConnect('/wearables/health-connect/summary','SYNTHETIC_PAIR_KEY')).rejects.toThrow('phone took too long');
    vi.mocked(fetch).mockResolvedValue({ok:false,status:502,json:async()=>({error:{code:'PRIVATE_MARKER'}})} as Response);
    await expect(api.requestHealthConnect('/wearables/health-connect/summary','SYNTHETIC_PAIR_KEY')).rejects.toThrow('request failed');
  });

  it.each([
    ['google_provider_unavailable','Google routing or place search'],
    ['google_secret_unavailable','AWS Secrets Manager'],
    ['storage_unavailable','AWS data store'],
  ])('explains known routing dependency %s without exposing the provider body',async(code,message)=>{
    const id='a'.repeat(32);
    vi.mocked(fetch).mockResolvedValue({ok:false,status:503,json:async()=>({error:{code,request_id:id,detail:'PRIVATE_MARKER'}})} as Response);
    await expect(api.request('/routes/preview',{},false)).rejects.toThrow(message);
    await expect(api.request('/routes/preview',{},false)).rejects.toThrow(`Reference: ${id}`);
  });

  it('rejects untrusted error codes and request references',async()=>{
    vi.mocked(fetch).mockResolvedValue({ok:false,status:503,json:async()=>({error:{code:'PRIVATE_MARKER',request_id:'SECRET_MARKER'}})} as Response);
    try{await api.request('/routes/preview',{},false);throw new Error('Expected failure');}
    catch(error){expect((error as Error).message).toBe('This service is not configured or temporarily unavailable.');}
  });
});
