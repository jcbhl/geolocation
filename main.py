import argparse
import plotly.graph_objects as go
import plotly.io as pio
from time import sleep
import requests
from collections import defaultdict
from tqdm import tqdm
import dns.resolver
import json

def handle_cli_args():
  parser = argparse.ArgumentParser(
                    prog = 'geolocator',
                    description = 'Given a HAR file exported from a browser\'s network dev tools, produce a map that shows all of the requests that went out.',
  )
  parser.add_argument('filename')
  return parser.parse_args()

def parse_har_file(filename: str):
  with open(filename) as f:
    parsed = json.load(f)
  
  return parsed

def get_hosts_from_harfile(harfile) -> set:
  hosts = set()
  for entry in harfile['log']['entries']:
    for header in entry['request']['headers']:
      if header['name'] == "Host":
        hosts.add(header['value'])
        break

  return hosts

# For each domain name in the set, run a DNS query to get the IP.
def do_dns_query(hostnames: set):
  res = defaultdict(lambda: [])

  for host in hostnames:
    for rdata in dns.resolver.query(host, 'A'):
      res[host].append(rdata.address)

  return res


# TODO need some sort of cache on disk since we get rate limited by the API 45 req/min
def get_geolocation(ip: str):
  url = f"https://ip-db.io/api/{ip}"
  response = requests.get(url)
  if response.status_code == 200:
    parsed = response.json()
    return parsed['latitude'], parsed['longitude']
  
  elif response.status_code == 429:
    print("Requests being throttled.")
    return None, None

def get_my_ip():
  url = "https://checkip.amazonaws.com/"
  response = requests.get(url)
  assert response.status_code == 200
  return response.text.strip()

def map_ips_to_geolocation(hosts):
  res = defaultdict(lambda: [])

  for domain, ips in tqdm(hosts.items()):
    for ip in ips:
      lat, long = get_geolocation(ip)
      print(f"found {lat}, {long} for domain {domain}")
      res[domain].append([lat, long])
      sleep(1.3)

  print(res)
  return res

def draw_map(geolocations: dict):
  my_lat, my_long = get_geolocation(get_my_ip())

  fig = go.Figure()

  for domain, latlong_array in geolocations.items():
    for lat, long in latlong_array:
      # Arc
      fig.add_trace(
        go.Scattergeo(
          locationmode = 'USA-states',
          lon = [my_long, long],
          lat = [my_lat, lat],
          mode = 'lines',
          line = dict(width = 1,color = 'red'),
          opacity = 1,
        )
      )
      
      # Endpoint
      fig.add_trace(go.Scattergeo(
        locationmode = 'USA-states',
        lon = [long],
        lat = [lat],
        hoverinfo = 'text',
        text = f"Domain {domain}",
        mode = 'markers',
        marker = dict(
            size = 10,
            color = 'rgb(255, 0, 0)',
            line = dict(
                width = 3,
                color = 'rgba(68, 68, 68, 0)'
            )
        )
      ))


  fig.update_layout(
    title_text = 'Request Geolocations',
    showlegend = False,
    geo = dict(
        showland = True,
        landcolor = 'rgb(243, 243, 243)',
        countrycolor = 'rgb(204, 204, 204)',
    ),
  )
  fig.update_geos(projection_type="orthographic", showcountries=True, countrycolor="Black")


  pio.write_html(fig, './images/test.html')
  # pio.write_image(fig, './images/test.png', format='png', scale=6, width=1080, height=1080)

  pass

def main():
  args = handle_cli_args()
  harfile = parse_har_file(args.filename)
  hostnames = get_hosts_from_harfile(harfile)
  hosts_with_addrs = do_dns_query(hostnames)
  # geolocations = map_ips_to_geolocation(hosts_with_addrs)

  draw_map(get_test_data())

  exit(0)



def get_test_data():
  return {
    'pagead2.googlesyndication.com': [[37.405991, -122.078514], [37.405991, -122.078514]], 
    'lightning.cnn.com': [[39.952339, -75.163788]], 
    'sync.search.spotxchange.com': [[39.88282, -105.106476], [39.88282, -105.106476]], 
    'events.brightline.tv': [[47.627499, -122.346199]], 
    'pixel-us-east.rubiconproject.com': [[39.04372, -77.487488], [39.04372, -77.487488]], 
    's.ntv.io': [[40.796768, -74.481537]], 
    'steadfastseat.com': [[29.941401, -95.344498]], 
    'aax-dtb-cf.amazon-adsystem.com': [[47.627499, -122.346199]], 
    'eq97f.publishers.tremorhub.com': [[39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488]], 
    'amplify.outbrain.com': [[40.796768, -74.481537]], 
    'www.cnn.com': [[57.707161, 11.96679]], 
    'mms.cnn.com': [[47.606209, -122.332069], [47.606209, -122.332069], [47.606209, -122.332069], [47.606209, -122.332069]], 
    'bea4.v.fwmrm.net': [[47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199]], 
    'cdn.cnn.com': [[39.952339, -75.163788]], 
    'clips-media-aka.warnermediacdn.com': [[39.952339, -75.163788], [39.952339, -75.163788]], 
    'z.cdp-dev.cnn.com': [[57.707161, 11.96679]], 
    'atom.warnermedia.com': [[39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488]], 
    'static.chartbeat.com': [[47.627499, -122.346199]], 
    'live.rezync.com': [[47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199]], 
    'fave.api.cnn.io': [[57.707161, 11.96679]], 
    'a6709203f34992a5095d2bc7ceaf2ec504f651a8.cws.conviva.com': [[37.552921, -122.26992]], 
    'licensing.bitmovin.com': [[39.099731, -94.578568]], 
    'cdn.krxd.net': [[57.707161, 11.96679]], 
    'www.i.cdn.cnn.com': [[57.707161, 11.96679]], 
    'tag.bounceexchange.com': [[39.099731, -94.578568]], 
    'get.s-onetag.com': [[47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199]], 
    'd2uap9jskdzp2.cloudfront.net': [[47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199], [47.627499, -122.346199]],
    'cdn.cookielaw.org': [[37.7757, -122.395203], [37.7757, -122.395203]], 
    'ib.adnxs.com': [[40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955], [40.739288, -73.984955]], 
    'www.summerhamster.com': [[39.04372, -77.487488], [39.04372, -77.487488]], 
    'data.cnn.com': [[57.707161, 11.96679]], 
    'ad.doubleclick.net': [[37.405991, -122.078514], [37.405991, -122.078514]], 
    'static.ads-twitter.com': [[57.707161, 11.96679]], 
    'c.amazon-adsystem.com': [[47.627499, -122.346199]], 
    'w.usabilla.com': [[39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488]], 
    'warnermediagroup-com.videoplayerhub.com': [[37.7757, -122.395203], [37.7757, -122.395203], [37.7757, -122.395203]], 
    'as-sec.casalemedia.com': [[32.783058, -96.806671], [32.783058, -96.806671]], 
    'services.brightline.tv': [[47.627499, -122.346199]], 
    'medium.ngtv.io': [[39.952339, -75.163788]], 
    'registry.api.cnn.io': [[57.707161, 11.96679]], 
    'clips-manifests-aka.warnermediacdn.com': [[39.952339, -75.163788], [39.952339, -75.163788]], 
    'www.ugdturner.com': [[39.04372, -77.487488], [39.04372, -77.487488], [39.04372, -77.487488]], 
    'image8.pubmatic.com': [[39.04372, -77.487488]], 
    'turnip.cdn.turner.com': [[39.952339, -75.163788], [39.952339, -75.163788]]
  }

if __name__ == "__main__":
  main()
