// Foreground rail centerline measured in the original 1672 x 941 artwork.
// Monotone cubic interpolation avoids angular jumps at traced control points.
const rail=[[-500,440],[0,511],[300,558],[600,603],[900,652],[1100,698],[1300,778],[1500,879],[1800,1050],[2200,1290]];
export function railAt(x:number){
 let j=0;while(j<rail.length-2&&x>rail[j+1][0])j++;
 const a=rail[j],b=rail[j+1],h=b[0]-a[0],t=(x-a[0])/h;
 const slope=(k:number)=>k===0?(rail[1][1]-rail[0][1])/(rail[1][0]-rail[0][0]):k===rail.length-1?(rail[k][1]-rail[k-1][1])/(rail[k][0]-rail[k-1][0]):(rail[k+1][1]-rail[k-1][1])/(rail[k+1][0]-rail[k-1][0]);
 const m0=slope(j),m1=slope(j+1);
 return {y:(2*t*t*t-3*t*t+1)*a[1]+(t*t*t-2*t*t+t)*h*m0+(-2*t*t*t+3*t*t)*b[1]+(t*t*t-t*t)*h*m1,
 slope:((6*t*t-6*t)*a[1]+(3*t*t-4*t+1)*h*m0+(-6*t*t+6*t)*b[1]+(3*t*t-2*t)*h*m1)/h};
}
export function trainPose(seconds:number,index:number){
 const x=-500+((seconds/68+.43+index*.5)%1)*2700;
 const scale=.76+Math.max(0,Math.min(1,x/1672))*.3;
 return {x,y:railAt(x).y,angle:Math.atan(railAt(x).slope)*180/Math.PI,scale};
}
export const STRIPS=40;
export const SPRITE_WIDTH=380;
// Visible wheel baseline in the transparent sprite at its displayed size.
export const wheelY=(u:number)=>72+.14*u;
export function stripPose(seconds:number,index:number,strip:number,reflection=false){
 const train=trainPose(seconds,index),u=strip*SPRITE_WIDTH/STRIPS;
 const x=train.x+(u-SPRITE_WIDTH/2)*train.scale;
 const rail=railAt(x),vertical=reflection?-train.scale*.46:train.scale;
 const shear=train.scale*rail.slope-vertical*.14;
 return {a:train.scale,b:shear,d:vertical,e:train.x-SPRITE_WIDTH/2*train.scale,
 f:rail.y-shear*u-vertical*wheelY(u),x,railY:rail.y};
}
