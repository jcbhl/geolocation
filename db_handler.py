# This site or product includes IP2Location LITE data available from https://lite.ip2location.com

from functools import lru_cache
import pandas as pd 
import ipaddress
import os

db: pd.DataFrame = None

def init_db():
  print("Loading geolocation database...")
  global db
  path = "db/IP2LOCATION-LITE-DB5.CSV"
  assert os.path.exists(path)
  field_names = ["ip_from", "ip_to", "country_code", "country_name", "region_name", "city_name", "latitude", "longitude"]
  db = pd.read_csv(path, names = field_names)
  print("Geolocation database loaded.")

def ipaddr_to_int(ip: str):
  return int(ipaddress.IPv4Address(ip))

@lru_cache(maxsize=None)
def get_geolocation(ip: str):
  assert db is not None
  target = ipaddr_to_int(ip)
  res = db.query("@target >= ip_from and @target <= ip_to")
  if res.shape[0] != 1:
    print(f"error: range query for ip {ip} returned {res.size} results.")
    print(res)

  row = res.values[0]
  lat = row[6]
  long = row[7]

  return lat, long
