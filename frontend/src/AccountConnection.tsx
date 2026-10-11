import {ArrowUpRight, Check, ShieldCheck, UserRound} from 'lucide-react';
import './account-connection.css';

type Props = {
  authenticated: boolean;
  busy: boolean;
  live: boolean;
  notice: string;
  onAuthenticate: () => void;
  onModeChange: (live: boolean) => void;
};

export default function AccountConnection({authenticated,busy,live,notice,onAuthenticate,onModeChange}:Props) {
  return <div className="account-connection">
    <div className="account-identity">
      <span className="account-avatar" aria-hidden="true"><UserRound size={24}/></span>
      <div><strong>{authenticated?'You’re signed in':'Browsing as a guest'}</strong><span>{authenticated?'Your account is connected.':'Route comparisons are available without an account.'}</span></div>
    </div>
    <p className="account-intro">{authenticated?'Access your private journeys, wearable readings and environmental alerts.':'Sign in to access your private journeys, wearable readings and environmental alerts.'}</p>
    <button className="primary-button account-sign-in" disabled={busy} onClick={onAuthenticate}>{busy?'Please wait…':authenticated?'Sign out':'Sign in securely'}<ArrowUpRight size={18}/></button>
    <p className="account-auth-provider"><ShieldCheck size={15}/><span>Account access secured by Amazon Cognito</span></p>
    {notice&&<p className="account-feedback" aria-live="polite">{notice}</p>}

    <section className="account-data-mode" aria-labelledby="account-data-title">
      <div className="account-section-heading"><h3 id="account-data-title">Your data view</h3><span>{live?'Live services':'Historical preview'}</span></div>
      <div className="mode-switch" role="group" aria-label="Data view">
        <button disabled={busy} aria-pressed={!live} className={!live?'selected':''} onClick={()=>onModeChange(false)}>Historical preview{!live&&<Check size={14}/>}</button>
        <button disabled={busy} aria-pressed={live} className={live?'selected':''} onClick={()=>onModeChange(true)}>Live services{live&&<Check size={14}/>}</button>
      </div>
      <p>{live?'Compare journeys using available provider data. Coverage and freshness are shown with your results.':'Explore a saved Delhi driving comparison from 9 October 2026. These readings describe that journey, not current conditions.'}</p>
    </section>

  </div>;
}
