#!/usr/bin/env python3
"""Conservative audit: green only for an exact available ePropertyPlus listing."""
import csv, json, re, time, datetime, urllib.parse, urllib.request, html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/metro-landbank-west-master.csv'
OUT=ROOT/'data/landbank-verification.json'
GIS='https://gis.lojic.org/maps/rest/services/LojicSolutions/OpenDataDevelopment/MapServer/18/query'
PORTAL='https://public-lky.epropertyplus.com/landmgmtpub/remote/public/property/viewSummary?parcelNumber='
def norm(s):
 s=str(s or '').upper()
 for a,b in [('STREET','ST'),('AVENUE','AVE'),('ROAD','RD'),('BOULEVARD','BLVD'),('DRIVE','DR'),('ALLEY','ALY'),('LANE','LN'),('PLACE','PL'),('COURT','CT')]:
  s=re.sub(r'\b'+a+r'\b',b,s)
 return re.sub('[^A-Z0-9]','',s)
def get(url,params=None):
 if params:url+='?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'User-Agent':'VAP-West-Listing-Audit/1.0 (public data verification)','Accept':'text/html,application/json'})
 with urllib.request.urlopen(req,timeout=25) as response:return response.read().decode('utf-8','replace')
def main():
 rows=list(csv.DictReader(SOURCE.open(newline='',encoding='utf-8')))
 result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Louisville ePropertyPlus individual listing pages','records':{},'counts':{}}
 try:
  by_addr={}
  for offset in range(0,100000,1000):
   payload=json.loads(get(GIS,{'where':'1=1','outFields':'PARCELID,PROP_ADDRESS','returnGeometry':'false','resultOffset':offset,'resultRecordCount':1000,'f':'json'}))
   if payload.get('error'):raise RuntimeError(str(payload['error']))
   features=payload.get('features',[])
   for f in features:
    a=f.get('attributes') or {};k=norm(a.get('PROP_ADDRESS'));pid=str(a.get('PARCELID') or '').strip()
    if k and pid:by_addr.setdefault(k,set()).add(pid)
   if len(features)<1000:break
 except Exception as e:
  print('GIS unavailable:',e);by_addr={}
 for i,row in enumerate(rows):
  address=row['address'];key=norm(address);parcels=sorted(by_addr.get(key,[]))
  item={'address':address,'owner':row['owner'],'neighborhood':row['neighborhood'],'status':'pending','reason':'No unique parcel match yet','parcel_id':'','listing_url':''}
  if len(parcels)>1:item['reason']='Multiple parcel IDs; needs manual resolution'
  elif len(parcels)==1:
   pid=parcels[0];item['parcel_id']=pid
   url=PORTAL+urllib.parse.quote(pid);item['reason']='Individual listing not yet verified'
   try:
    page=get(url);plain=html.unescape(re.sub(r'<[^>]*>',' ',page));plain=re.sub(r'\s+',' ',plain)
    address_ok=key in norm(plain)
    parcel_ok=pid in re.sub(r'[^A-Z0-9]','',plain.upper())
    available=bool(re.search(r'Property Status\s*Available\b',plain,re.I))
    not_found=bool(re.search(r'Property Not Found|Page Not Found|No longer found|404 Not Found',plain,re.I))
    if address_ok and parcel_ok and available and not not_found:
     item.update(status='verified',reason='Exact parcel, address and Available status confirmed on listing page',listing_url=url)
    elif not_found:item.update(status='pending',reason='Constructed parcel URL returned not found; portal listing status unknown')
    elif address_ok and parcel_ok:item.update(status='pending',reason='Listing found but availability not confirmed')
    else:item['reason']='Listing page did not confirm exact address and parcel'
   except Exception as e:item['reason']='Listing lookup unavailable: '+str(e)[:120]
  result['records'][key]=item
  result['counts'][item['status']]=result['counts'].get(item['status'],0)+1
  if i%30==0:print('Processed',i+1,'/',len(rows))
 OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('Final counts',result['counts'])
if __name__=='__main__':main()
