// Default departure is calculated at submission, not when the page was opened.
export function routeDeparture(planned:string|null,now=new Date()):string {
  if(planned===null)return new Date(now.getTime()+60000).toISOString();
  const stamp=new Date(planned);
  if(!Number.isFinite(stamp.getTime()))throw new Error('Choose a valid departure date and time.');
  if(stamp.getTime()<now.getTime()-5*60000||stamp.getTime()>now.getTime()+48*3600000)throw new Error('Choose a departure within the next 48 hours.');
  return stamp.toISOString();
}
