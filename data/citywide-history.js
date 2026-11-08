(async()=>{
const count=document.getElementById('closedCount'),box=document.getElementById('lyr-closed');
const history=L.layerGroup(),groups=new Map();
try{
const paths=Array.from({length:10},(_,i)=>'./data/vap-closed-'+String(i).padStart(2,'0')+'.txt');
const batches=await Promise.all(paths.map(async path=>{
 const r=await fetch(path);if(!r.ok)throw Error(path+' HTTP '+r.status);
 const raw=(await r.text()).replace(/\s/g,'');
 const bytes=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
 return JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
}));
let total=0;
for(const batch of batches)for(const rec of batch){
total++;
const [id,address,status,statusDate,type,dateOpened,lat,lng]=rec;
if(!Number.isFinite(lat)||!Number.isFinite(lng)||!address)continue;
const key=String(address).toUpperCase().replace(/[^A-Z0-9]/g,'');
let g=groups.get(key);if(!g){g={address,lat,lng,records:[]};groups.set(key,g)}
g.records.push({id,status,statusDate,type,dateOpened});
}
const layerRenderer=L.canvas({padding:.5});
for(const g of groups.values()){
const point=L.circleMarker([g.lat,g.lng],{renderer:layerRenderer,radius:4,weight:1,color:'#41296c',fillColor:'#8256bd',fillOpacity:.82});
point.bindPopup(()=>{
const d=document.createElement('div'),h=document.createElement('strong');h.textContent=g.address;d.append(h);
const p=document.createElement('p');p.textContent=g.records.length+' historical closed work-order records';d.append(p);
const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='View records and dates';details.append(summary);
for(const rec of g.records){const line=document.createElement('div');line.style.cssText='padding:6px 0;border-bottom:1px solid #ddd';line.textContent=[rec.id,rec.type,rec.status,rec.dateOpened,rec.statusDate].filter(Boolean).join(' · ');details.append(line)}
d.append(details);return d;
});history.addLayer(point);
}
count.textContent=groups.size.toLocaleString()+' properties';
box.addEventListener('change',()=>{if(box.checked)history.addTo(map);else map.removeLayer(history)});
if(box.checked)history.addTo(map);
}catch(e){console.error('Historical CSV layer',e);count.textContent='Load error';}
})();