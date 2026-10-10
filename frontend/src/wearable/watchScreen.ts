import type {WatchData,WatchPage,WatchSettings} from './watchData';

// Original canvas artwork, rendered as a texture on the physical 3D display.
export function paintScreen(canvas:HTMLCanvasElement,page:WatchPage,d:WatchData|undefined,s:WatchSettings,now:Date){
 const c=canvas.getContext('2d')!;const a=s.accent;c.setTransform(canvas.width/512,0,0,canvas.height/600,0,0);
 c.clearRect(0,0,512,600);c.fillStyle='#050b10';c.fillRect(0,0,512,600);
 const text=(value:string,x:number,y:number,size=28,color='#eef8ff',align:CanvasTextAlign='left',maxWidth?:number)=>{
  // Fit each label to its own safe box, rather than letting glyphs reach the bevel.
  const available=Math.max(1,maxWidth??(align==='center'?Math.min(x-36,476-x)*2:align==='right'?x-36:476-x));
  let fontSize=Math.max(26,size);c.font=`600 ${fontSize}px Manrope, sans-serif`;
  const width=c.measureText(value).width;if(width>available){fontSize*=available/width;c.font=`600 ${fontSize}px Manrope, sans-serif`;}
  c.save();c.beginPath();c.rect(align==='center'?x-available/2:align==='right'?x-available:x,y-fontSize-3,available,fontSize+9);c.clip();
  c.fillStyle=color;c.textAlign=align;c.fillText(value,x,y);c.restore();
 };
 const card=(x:number,y:number,w:number,h:number)=>{c.fillStyle='#111e28';c.beginPath();c.roundRect(x,y,w,h,20);c.fill();};
 const ring=(x:number,y:number,r:number,p:number,color:string,width=12)=>{c.lineWidth=width;c.lineCap='round';c.strokeStyle='#20323d';c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.stroke();c.strokeStyle=color;c.beginPath();c.arc(x,y,r,-Math.PI/2,Math.PI*2*p/100-Math.PI/2);c.stroke();};
 if(!d&&page!=='Settings'){
  text('ECOROUTE',48,44,25);text(page,40,110,38);
  if(page==='Home'){text(now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false}),40,215,78);text(now.toLocaleDateString([],{day:'numeric',month:'short'}),40,260,28,'#d2e3ec');}
  ring(256,365,62,0,'#55626c',7);text('—',256,380,54,'#d2e3ec','center');
  text(page==='Notifications'?'No notifications':'No readings available',256,482,30,'#ffffff','center');
  text('Watch not connected',256,533,27,'#c4d9e4','center');return;
 }
 if(!d){
  text('Settings',40,95,38);[['THEME',a==='#ff914d'?'Transit':a==='#58ddeb'?'Glacier':'Volt'],['BRIGHTNESS',`${s.brightness}%`],['IDLE MOTION',s.motion?'On':'Off']].forEach(([label,value],i)=>{const y=150+i*110;card(26,y,460,90);text(label,46,y+32,26);text(value,464,y+67,30,a,'right');});return;
 }
 text('ECOROUTE',48,44,25,'#d2e3ec');text(`${d.battery}% ▰`,464,44,25,'#bff7cd','right');
 const title=(value:string)=>text(value,30,92,30);
 if(page==='Home'){
  text(now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false}),28,123,76);
  text(now.toLocaleDateString([],{weekday:'short',day:'numeric',month:'short'}).toUpperCase(),32,157,27,'#d2e3ec');
  ring(256,280,88,d.health,a);ring(256,280,69,d.activity,'#a5ee80',5);
  text(String(d.health),256,290,67,'#f4ffff','center');text('HEALTH',256,321,26,'#d2e3ec','center',124);
  [[`♥ ${d.heartRate} BPM`,'HEART'],[d.steps.toLocaleString('en-US'),'STEPS'],[`${d.calories} kcal`,'ENERGY'],[`${d.sleep} / 100`,'SLEEP']].forEach(([value,label],i)=>{const x=26+(i%2)*237,y=390+Math.floor(i/2)*75;card(x,y,223,67);text(value,x+15,y+31,34,i===0?'#ff93b5':'#eef8ff','left',193);text(label,x+15,y+57,26,'#c4d9e4','left',193);});
  text(`SpO2 ${d.oxygen}%`,30,575,18,a);text('SAMPLE',480,575,25,'#9aafb9','right');
 }else if(page==='Heart'){
  title('Heart rhythm');text('♥',256,186,64+(s.motion?Math.sin(now.getTime()/170)*4:0),'#ff7da6','center');text(String(d.heartRate),256,287,110,'#fff','center');text('BEATS / MINUTE',256,325,20,'#a8b4c1','center');
  c.strokeStyle='#ff7da6';c.lineWidth=4;c.lineJoin='round';c.beginPath();[[28,410],[85,410],[106,397],[125,425],[147,410],[174,410],[192,351],[212,466],[232,400],[255,412],[295,412],[320,394],[343,423],[366,410],[395,410],[415,370],[435,445],[453,408],[484,408]].forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.stroke();
  text('ILLUSTRATIVE PULSE',256,513,19,'#b4a6b2','center');text('No sensor connected',256,552,22,'#90a6b7','center');
 }else if(page==='Activity'){
  title('Keep moving');ring(256,244,110,d.activity,a,18);ring(256,244,84,65,'#a5ee80',15);ring(256,244,61,54,'#799dff',12);text(`${d.activity}%`,256,254,42,'#fff','center');
  text(d.steps.toLocaleString('en-US'),256,433,72,'#fff','center');text('DAILY STEPS',256,469,20,'#a5b8c4','center');card(38,499,436,62);text(`${d.calories} kcal`,58,538,30,'#eef8ff','left',195);text('SAMPLE',452,538,26,a,'right',140);
 }else if(page==='Sleep'){
  title('Night recovery');ring(256,270,116,d.sleep,'#b5a7ff',15);text(String(d.sleep),256,286,86,'#fff','center');text('SLEEP / 100',256,323,20,'#bdb5dc','center');text(d.sleepDuration,256,451,52,'#d7cfff','center');text('Restful · sample quality',256,505,23,'#acb8cf','center');text('Not a clinical assessment',256,554,18,'#8499aa','center');
 }else if(page==='Wellness'){
  title('Wellness');text('SpO2',256,166,25,a,'center');text(`${d.oxygen}%`,256,266,96,'#fff','center');text('BLOOD OXYGEN',256,313,20,'#9cb6c6','center');card(30,363,452,142);text('Hydration preview',54,405,24);ring(416,436,40,d.hydration,a,9);text(`${d.hydration}%`,54,462,43,a);text('Sample · not measured',256,559,18,'#96a9b6','center');
 }else if(page==='Notifications'){
  title('EcoRoute updates');const messages=s.previewAlerts?[['ROUTE PLANNING','Compare air coverage','before your next journey.'],['YOUR PRIVACY','Bridge not connected.','Consent stays with you.'],['SAMPLE PREVIEW','No notifications sent.','No live alert triggered.']]:[['PREVIEW MUTED','Sample cards are paused.','Live settings unchanged.']];
  messages.forEach(([heading,line1,line2],i)=>{const y=125+i*137;card(26,y,460,120);text(heading,46,y+30,26,a,'left',416);text(line1,46,y+64,28,'#eef8ff','left',416);text(line2,46,y+96,26,'#c4d9e4','left',416);});
 }else{
  title('Make it yours');[['THEME',a==='#ff914d'?'Transit':a==='#58ddeb'?'Glacier':'Volt'],['BRIGHTNESS',`${s.brightness}%`],['IDLE MOTION',s.motion?'On':'Off'],['PREVIEW ALERTS',s.previewAlerts?'On':'Off']].forEach(([label,value],i)=>{const y=125+i*93;card(26,y,460,80);text(label,46,y+31,16,'#90a8b7');text(value,464,y+53,27,a,'right');});text('Use controls below',256,559,19,'#9bb1c0','center');
 }
}
