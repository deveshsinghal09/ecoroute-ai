import {test,expect} from '@playwright/test';
for(const size of [{width:1280,height:720},{width:1366,height:768},{width:1024,height:640},{width:390,height:844}]){
 test(`sidebar fits ${size.width}x${size.height}`,async({page})=>{
 await page.setViewportSize(size);await page.goto('/');
 await expect(page.getByTestId('selected-pm25')).toBeVisible();
 await page.evaluate(()=>document.fonts.ready);
 const problems=await page.locator('.instrument-rail').evaluate(rail=>{
 const issues:string[]=[];
 for(const card of rail.children){const b=card.getBoundingClientRect();if(innerWidth>740&&b.bottom>rail.getBoundingClientRect().bottom+1)issues.push(card.className+' exceeds rail by '+Math.round(b.bottom-rail.getBoundingClientRect().bottom));for(const child of card.querySelectorAll('*')){if(child.closest('svg'))continue;const r=child.getBoundingClientRect();if(r.width&&r.height&&(r.left<b.left-1||r.right>b.right+1||r.bottom>b.bottom+1))issues.push(child.className||child.tagName);}}
 if(innerWidth>740&&rail.getBoundingClientRect().bottom>innerHeight)issues.push('rail exceeds viewport');return issues;
 });expect(problems).toEqual([]);
 const readability=await page.locator('.instrument-rail').evaluate(rail=>{
   const failures:string[]=[];
   const rgb=(color:string)=>color.match(/[\d.]+/g)!.slice(0,3).map(Number);
   const luminance=(color:string)=>rgb(color).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   for(const el of rail.querySelectorAll('p,.rail-small,.small-badge,.selected-route-context span,.selected-coverage-row span')){
     if(!el.getBoundingClientRect().height)continue;
     const style=getComputedStyle(el);if(parseFloat(style.fontSize)<11)failures.push('small text: '+el.className);
     let parent:Element|null=el,bg='';
     while(parent){const c=getComputedStyle(parent).backgroundColor;if(c!=='rgba(0, 0, 0, 0)'){bg=c;break;}parent=parent.parentElement;}
     if(bg){const a=luminance(style.color),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(ratio<4.5)failures.push('low contrast: '+el.className);}
   }
   return failures;
 });expect(readability).toEqual([]);
 await page.getByRole('button',{name:'Insights',exact:true}).click();
 await expect(page.getByText('Check forecasting model',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Completed local training evaluation',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Sources & route limitations',{exact:true})).toHaveCount(0);
 if(size.width===1280)await page.screenshot({path:'../work/sidebar-spacing-fixed.png'});
 });
}
