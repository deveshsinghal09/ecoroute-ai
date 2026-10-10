import { useEffect, useRef, useState } from 'react';
import './SmartwatchHealth.css';

// Physical watch adapted from Sparsh Gupta's SmartWatch (PURE CSS):
// https://codepen.io/sparshgupta007/pen/abJZoVx. See docs/SMARTWATCH_UI.md.
export const demoHealth = Object.freeze({
  healthScore: 87, heartRate: 76, bloodOxygen: 98, sleepScore: 92,
  sleepDuration: '7h 42m', steps: 8420, calories: 324, activityProgress: 78,
});
const screens = ['Home', 'Heart health', 'Sleep', 'Activity'];

function Ring({ value, color, children, small = false }) {
  return <div className={`swh-ring ${small ? 'swh-ring-small' : ''}`} style={{ '--ring-color': color }}>
    <svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="43" className="swh-ring-track"/><circle cx="50" cy="50" r="43" pathLength="100" strokeDasharray={`${Math.max(0, Math.min(100, value))} 100`} className="swh-ring-value"/></svg>
    <div>{children}</div>
  </div>;
}

/** Presentation only: values are explicitly demo data, never sent to telemetry APIs. */
export default function SmartwatchHealth({ data = demoHealth }) {
  const [screen, setScreen] = useState(0);
  const [now, setNow] = useState(() => new Date());
  const start = useRef(null);
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 15000); return () => clearInterval(timer); }, []);
  const next = (direction) => setScreen(current => (current + direction + screens.length) % screens.length);
  function finishSwipe(event) {
    if (!start.current) return;
    const dx = event.clientX - start.current.x, dy = event.clientY - start.current.y;
    start.current = null;
    if (Math.abs(dx) > 30 && Math.abs(dx) > Math.abs(dy)) next(dx < 0 ? 1 : -1);
  }
  return <section className="smartwatch-health" aria-label="Interactive smartwatch demo">
    <div className="swh-label"><span className="swh-demo-dot"/> DEMO HEALTH DATA <span>Not connected</span></div>
    <div className="swh-watch-container">
      <div className="swh-watch">
        <div className="swh-dial">
          <div className="swh-reflection"/>
          <button className="swh-home-btn" aria-label="Watch home" onClick={() => setScreen(0)}/>
          <div className="swh-dial-face" tabIndex={0} role="group" aria-label={`${screens[screen]} watch screen. Swipe or use arrow keys to change screen.`}
            onPointerDown={event => { if (event.target.closest('button')) return; start.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId); }}
            onPointerUp={finishSwipe} onPointerCancel={() => { start.current = null; }}
            onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) { event.preventDefault(); if (event.key === 'Home') setScreen(0); else next(event.key === 'ArrowRight' ? 1 : -1); } }}>
            <div className="swh-status"><span>DEMO</span><time>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}</time><span aria-label="Demo battery">▰</span></div>
            <div className="swh-screen" key={screen} aria-live="polite">
              {screen === 0 && <><span className="swh-screen-title">Your daily balance</span><Ring value={data.healthScore} color="#b8ec7a"><strong>{data.healthScore}<small>/100</small></strong><span>Health score</span></Ring><div className="swh-mini"><span>♥ {data.heartRate} <small>BPM</small></span><span>↗ {data.activityProgress}%</span></div><span className="swh-oxygen">Blood oxygen <b>{data.bloodOxygen}%</b></span></>}
              {screen === 1 && <><span className="swh-screen-title">Heart health</span><div className="swh-pulse" aria-hidden="true">♥</div><div className="swh-reading">{data.heartRate}<small>BPM</small></div><svg className="swh-graph" viewBox="0 0 180 40" role="img" aria-label="Illustrative pulse graph, not measured heart rate"><path d="M0 25 H20 L26 22 L32 27 H45 L51 25 L57 7 L64 37 L70 21 L76 25 H95 L103 23 L110 27 H126 L132 25 L139 6 L147 36 L154 23 L161 25 H180"/></svg><span className="swh-muted">Illustrative pulse · no sensor</span><span className="swh-oxygen">Blood oxygen <b>{data.bloodOxygen}%</b></span></>}
              {screen === 2 && <><span className="swh-screen-title">Sleep</span><Ring value={data.sleepScore} color="#b7a5ff"><strong>{data.sleepScore}<small>/100</small></strong><span>Sleep score</span></Ring><div className="swh-sleep-duration">☾ {data.sleepDuration}</div><span className="swh-muted">Demo sleep duration</span></>}
              {screen === 3 && <><span className="swh-screen-title">Activity</span><Ring value={data.activityProgress} color="#ff914d" small><strong>{data.activityProgress}<small>%</small></strong></Ring><div className="swh-steps">{data.steps.toLocaleString('en-US')}<span>DAILY STEPS</span></div><div className="swh-mini"><span>↗ Move {data.activityProgress}%</span><span>{data.calories} kcal</span></div></>}
            </div>
            <div className="swh-screen-dots" aria-label="Watch screens">{screens.map((name, index) => <button key={name} aria-label={`Show ${name}`} aria-pressed={screen === index} onClick={() => setScreen(index)}/>)}</div>
          </div>
          <span className="swh-branding">ecoroute</span>
        </div>
        <div className="swh-strap swh-top-strap" aria-hidden="true"><div className="swh-buckle"><span className="swh-shadows"/><span className="swh-buckle-shadow"/></div><div className="swh-rect-fit"/></div>
        <div className="swh-strap swh-bottom-strap" aria-hidden="true"><div className="swh-hole-container">{Array.from({ length: 8 }, (_, i) => <span className="swh-hole" key={i}/>)}</div></div>
      </div>
    </div>
    <div className="swh-controls"><button aria-label="Previous watch screen" onClick={() => next(-1)}>←</button><span>{screens[screen]}<small>Swipe screen to explore</small></span><button aria-label="Next watch screen" onClick={() => next(1)}>→</button></div>
    <p className="swh-disclosure">All health values are placeholders, not measurements or medical assessments.</p>
    <a className="swh-credit" href="https://codepen.io/sparshgupta007/pen/abJZoVx" target="_blank" rel="noreferrer">Watch design · Sparsh Gupta</a>
  </section>;
}
