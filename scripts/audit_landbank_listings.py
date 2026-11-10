#!/usr/bin/env python3
"""Verify published Louisville listings; GIS ownership never establishes availability."""
import csv, json, re, datetime, urllib.parse, urllib.request, html
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://public-lky.epropertyplus.com'
API = BASE + '/landmgmtpub/remote/public/property/'
def norm(value):
    value = str(value or '').upper()
    for a, b in [('SAINT','ST'),('STREET','ST'),('AVENUE','AVE'),('ROAD','RD'),('BOULEVARD','BLVD'),('DRIVE','DR'),('ALLEY','ALY'),('LANE','LN'),('PLACE','PL'),('COURT','CT')]:
        value = re.sub(r'\b'+a+r'\b', b, value)
    return re.sub('[^A-Z0-9]', '', value)
def get(url, params=None):
    if params: url += '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent':'VAP-West-Listing-Audit/2.0','Accept':'application/json,text/html'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8'), response.geturl()
def published():
    rows = []
    for offset in range(0, 100000, 250):
        raw, _ = get(API+'getPublishedProperties', {'limit':250,'page':offset//250+1,'iDisplayStart':offset,'iDisplayLength':250,'json':json.dumps({'criterias':[]})})
        page = json.loads(raw)
        if page.get('success') is not True: raise RuntimeError('Published inventory failed')
        part = page.get('rows', [])
        rows.extend(part)
        if len(rows) >= page['size']: break
        if not part: raise RuntimeError('Incomplete inventory pagination')
    if len(rows) != page['size'] or len({r['parcelNumber'] for r in rows}) != len(rows):
        raise RuntimeError('Incomplete or duplicate inventory; preserving previous audit')
    return rows

def verify(pair):
    key, (source, hits) = pair
    item = {'address':source['address'],'owner':source['owner'],'neighborhood':source['neighborhood'], 'status':'pending','reason':'No exact address match in published inventory; availability unknown','parcel_id':'','listing_url':''}
    if len(hits) != 1:
        if hits: item['reason'] = 'Multiple published parcels match this address; manual review required'
        return key, item
    row = hits[0]
    parcel = row['parcelNumber']
    item.update(parcel_id=parcel, portal_status=row['currentStatus'], property_id=row['id'])
    try:
        detail_url = API+'getPublishedPropertyByParcelNumber?'+urllib.parse.urlencode({'parcelNumber':parcel})
        raw, _ = get(detail_url)
        detail = json.loads(raw)
        record = detail.get('returnVal') or {}
        if detail.get('success') is not True or record.get('parcelNumber') != parcel or norm(record.get('propertyAddress1')) != key or record.get('currentStatus') != row['currentStatus']:
            raise RuntimeError('Published detail does not confirm address, parcel and status')
        # The candidate is never exposed until the returned page confirms its identity
        # and supplies the same exact URL in its canonical Open Graph metadata.
        candidate = API+'viewSummary?'+urllib.parse.urlencode({'parcelNumber':parcel})
        page, final_url = get(candidate)
        metas = dict((name, html.unescape(value)) for name, value in re.findall(r'<meta\s+property="([^"]+)"\s+content="([^"]*)"', page))
        if final_url != candidate or metas.get('og:url') != candidate or norm(metas.get('og:title','').split(',')[0]) != key:
            raise RuntimeError('Listing page did not confirm canonical URL and exact address')
        item.update(listing_url=metas['og:url'], current_property_url=BASE+'/property/'+urllib.parse.quote(parcel,safe=''), current_property_url_check='Current portal detail route pattern confirmed in a live browser; parcel ID matched from published inventory.', detail_url=detail_url, link_verified=True)
        if row['currentStatus'] == 'Available':
            item.update(status='verified', reason='Published inventory and exact property detail confirm Available; canonical listing page verified')
        else:
            item.update(status='program', reason='Official published listing has status '+row['currentStatus']+'; not counted as Available')
    except Exception as exc:
        item['reason'] = 'Individual verification failed: '+str(exc)[:180]
    return key, item

def main():
    sources = list(csv.DictReader((ROOT/'data/metro-landbank-west-master.csv').open(newline='',encoding='utf-8')))
    rows = published()
    index = defaultdict(list)
    for row in rows: index[norm(row['propertyAddress1'])].append(row)
    unique = {norm(row['address']):row for row in sources}
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = dict(pool.map(verify, ((key,(source,index[key])) for key,source in unique.items())))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = {'checked_at':now,'source':'Louisville ePropertyPlus published inventory, exact property details and canonical listing pages','inventory_endpoint':API+'getPublishedProperties','source_rows':len(sources),'unique_source_addresses':len(unique),'duplicate_source_rows':len(sources)-len(unique),'published_total':len(rows),'published_status_counts':dict(Counter(row['currentStatus'] for row in rows)),'counts':dict(Counter(item['status'] for item in records.values())),'row_counts':dict(Counter(records[norm(row['address'])]['status'] for row in sources)),'records':records}
    out = ROOT/'data/landbank-verification.json'
    temp = out.with_suffix('.tmp')
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    temp.replace(out)
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2), flush=True)
if __name__ == '__main__': main()
