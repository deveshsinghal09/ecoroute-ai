// Stable route identities across map paths, legend and comparison cards.
export const routeColors=['#df4e13','#2563eb','#7c3aed','#087f8c'] as const;
export function routeColor(index:number){return routeColors[index%routeColors.length];}
