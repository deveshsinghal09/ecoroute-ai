// Rail centerline traced in the backdrop's 1672 x 941 coordinate space.
const rail=[[ -500,457],[0,517],[300,553],[600,592],[900,638],[1100,681],[1300,745],[1500,833],[1800,990],[2200,1230]];
export function trainPose(seconds:number,index:number){
  // Equal velocity and half-loop separation prevent overtaking and collisions.
  const x=-500+((seconds/68+.43+index*.5)%1)*2700;
  let j=0;while(j<rail.length-2&&x>rail[j+1][0])j++;
  const [a,b]=[rail[j],rail[j+1]],t=(x-a[0])/(b[0]-a[0]);
  const slope=(b[1]-a[1])/(b[0]-a[0]);
  const scale=.76+Math.max(0,Math.min(1,x/1672))*.3;
  // Sprite contact baseline sits 32 units above its box bottom and slopes 8 degrees.
  return {x,y:a[1]+t*(b[1]-a[1])+32*scale,angle:Math.atan(slope)*180/Math.PI-8,scale};
}
