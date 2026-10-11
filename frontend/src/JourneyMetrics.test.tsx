import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import JourneyMetrics from './JourneyMetrics';
import {historical,type Route} from './data';

// Artificial metric values exercise UI contracts only; never production readings.
const route=(changes:Partial<Route>={})=>({...historical.routes[0],duration_s:360,estimated_pm25_exposure_ug_h_m3:8,pm25_coverage_fraction:1,...changes});
describe('selected route instruments',()=>{
  it('derives concentration, exposure and journey context from the supplied route',()=>{
    const a=renderToStaticMarkup(<JourneyMetrics route={route()} routeIndex={0} live sharedForecast={false}/>);
    const b=renderToStaticMarkup(<JourneyMetrics route={route({duration_s:720,estimated_pm25_exposure_ug_h_m3:12})} routeIndex={1} live sharedForecast={false}/>);
    expect(a).toContain('Route 1 selected');expect(a).toContain('data-testid="selected-pm25">80.0');expect(a).toContain('data-testid="selected-exposure">8.00');
    expect(b).toContain('Route 2 selected');expect(b).toContain('data-testid="selected-pm25">60.0');expect(b).toContain('data-testid="selected-exposure">12.00');
  });
  it('preserves matching concentrations when longer routes share a forecast cell',()=>{
    const a=renderToStaticMarkup(<JourneyMetrics route={route()} routeIndex={0} live sharedForecast/>);
    const b=renderToStaticMarkup(<JourneyMetrics route={route({duration_s:720,estimated_pm25_exposure_ug_h_m3:16})} routeIndex={1} live sharedForecast/>);
    expect(a).toContain('data-testid="selected-pm25">80.0');expect(b).toContain('data-testid="selected-pm25">80.0');
    expect(b).toContain('data-testid="selected-exposure">16.00');expect(b).toContain('PM2.5 may match across routes.');
  });
  it('keeps missing concentrations unavailable and renders real zero values',()=>{
    const missing=renderToStaticMarkup(<JourneyMetrics route={route({estimated_pm25_exposure_ug_h_m3:null,pm25_coverage_fraction:0})} routeIndex={1} live sharedForecast/>);
    expect(missing).toContain('data-testid="selected-exposure">—');expect(missing).toContain('data-testid="selected-coverage">0');expect(missing).not.toContain('Same forecast cell');
    const zero=renderToStaticMarkup(<JourneyMetrics route={route({estimated_pm25_exposure_ug_h_m3:0})} routeIndex={0} live sharedForecast={false}/>);
    expect(zero).toContain('data-testid="selected-pm25">0.0');expect(zero).toContain('data-testid="selected-exposure">0.00');
  });
});
