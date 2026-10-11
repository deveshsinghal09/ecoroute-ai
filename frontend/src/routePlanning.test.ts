import {it,expect} from 'vitest';
import {routeDeparture} from './routePlanning';
it('leave now uses the submission clock even after a long session',()=>{
 expect(routeDeparture(null,new Date('2026-10-12T09:00:00Z'))).toBe('2026-10-12T09:01:00.000Z');
 expect(routeDeparture(null,new Date('2026-10-12T11:00:00Z'))).toBe('2026-10-12T11:01:00.000Z');
});
it('planned departures preserve timezone conversion',()=>{
 expect(routeDeparture('2026-10-12T16:30:00+05:30',new Date('2026-10-12T09:00:00Z'))).toBe('2026-10-12T11:00:00.000Z');
});
it('invalid, old and out-of-range departure choices are rejected',()=>{
 const now=new Date('2026-10-12T09:00:00Z');
 for(const value of ['bad date','2026-10-11T09:00:00Z','2026-10-15T09:00:00Z'])expect(()=>routeDeparture(value,now)).toThrow();
});
