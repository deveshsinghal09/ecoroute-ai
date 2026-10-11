import {test,expect} from '@playwright/test';
for(const size of [{width:1280,height:720},{width:1366,height:768},{width:1024,height:640},{width:390,height:844}]){
 test(`sidebar fits ${size.width}x${size.height}`,async({page})=>{
 await page.setViewportSize(size);await page.goto('/');
 await expect(page.getByTestId('selected-pm25')).toBeVisible();
 const problems=await page.locator('.instrument-rail').evaluate(rail=>{
 const issues:string[]=[];
 for(const card of rail.children){const b=card.getBoundingClientRect();for(const child of card.querySelectorAll('*')){if(child.closest('svg'))continue;const r=child.getBoundingClientRect();if(r.width&&r.height&&(r.left<b.left-1||r.right>b.right+1||r.bottom>b.bottom+1))issues.push(child.className||child.tagName);}}
 if(innerWidth>740&&rail.getBoundingClientRect().bottom>innerHeight)issues.push('rail exceeds viewport');return issues;
 });expect(problems).toEqual([]);
 await page.getByRole('button',{name:'Insights',exact:true}).click();
 await expect(page.getByText('Check forecasting model',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Completed local training evaluation',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Sources & route limitations',{exact:true})).toHaveCount(0);
 if(size.width===1280)await page.screenshot({path:'../work/sidebar-spacing-fixed.png'});
 });
}
