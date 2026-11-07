#!/usr/bin/env python3
"""Build auditable West End work-order export with Census tract/neighborhood crosswalk.
Requires: pandas, geopandas, requests, shapely.
Run: python build_west_end_workorders.py pm_workorder_closed.csv
"""
import sys, json
from pathlib import Path
import pandas as pd
import geopandas as gpd
import requests

NEIGHBORHOODS = ['RUSSELL','SHAWNEE','PORTLAND','CHICKASAW','PARKLAND','CALIFORNIA','PARK HILL','ALGONQUIN','TAYLOR BERRY']
LOJIC = 'https://gis.lojic.org/maps/rest/services/LojicApps/Neighborhoods/FeatureServer/0/query'
CENSUS = 'https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_21_tract.zip'

def fetch_neighborhoods():
    params = {'where':"NH_NAME IN ("+','.join("'"+n+"'" for n in NEIGHBORHOODS)+")",
              'outFields':'NH_NAME','outSR':4326,'returnGeometry':'true','f':'geojson'}
    r=requests.get(LOJIC,params=params,timeout=90);r.raise_for_status()
    payload=r.json()
    if 'features' not in payload or len(payload['features'])!=9:
        raise ValueError('Expected nine LOJIC neighborhood polygons; got '+str(len(payload.get('features',[]))))
    p=Path('west_neighborhoods.geojson');p.write_text(json.dumps(payload))
    return gpd.read_file(p).to_crs(4326)

def main(path):
    raw=pd.read_csv(path,low_memory=False)
    raw['STATUS_DATE']=pd.to_datetime(raw['STATUS_DATE'],errors='coerce')
    raw=raw.loc[raw['STATUS_DATE'].between('2023-11-07','2026-11-07 23:59:59') & raw['RECORD_STATUS'].eq('Closed')].copy()
    raw['LATITUDE']=pd.to_numeric(raw['LATITUDE'],errors='coerce')
    raw['LONGITUDE']=pd.to_numeric(raw['LONGITUDE'],errors='coerce')
    missing=raw.loc[raw[['LATITUDE','LONGITUDE']].isna().any(axis=1)]
    pts=gpd.GeoDataFrame(raw.drop(missing.index),geometry=gpd.points_from_xy(raw.drop(missing.index).LONGITUDE,raw.drop(missing.index).LATITUDE),crs='EPSG:4326')
    hoods=fetch_neighborhoods()
    assigned=gpd.sjoin(pts,hoods[['NH_NAME','geometry']],how='inner',predicate='intersects').drop(columns=['index_right'])
    tracts=gpd.read_file(CENSUS).to_crs(4326)
    tracts=tracts.loc[tracts['COUNTYFP'].eq('111') & tracts['STATEFP'].eq('21'),['GEOID','geometry']]
    matched=gpd.sjoin(assigned,tracts,how='left',predicate='intersects').drop(columns=['index_right'])
    matched=matched.rename(columns={'NH_NAME':'neighborhood','GEOID':'census_tract_geoid'})
    matched=matched.drop_duplicates(subset=['ObjectId','neighborhood','census_tract_geoid'])
    matched.drop(columns='geometry').to_csv('west_end_closed_workorders_2023_2026.csv',index=False)
    crosswalk=matched.groupby(['neighborhood','census_tract_geoid'],dropna=False).agg(work_orders=('ObjectId','nunique')).reset_index()
    crosswalk.to_csv('west_end_neighborhood_census_crosswalk.csv',index=False)
    print('Matched rows:',len(matched),'Unique orders:',matched.ObjectId.nunique(),'Missing-coordinate records excluded:',len(missing))
    print(matched.groupby('neighborhood').ObjectId.nunique().to_string())

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python build_west_end_workorders.py pm_workorder_closed.csv')
    main(sys.argv[1])
