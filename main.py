import argparse
import plotly.graph_objects as go
from functools import lru_cache
from datetime import datetime
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

def get_domain_from_entry(entry) -> str:
  for header in entry['request']['headers']:
    if header['name'] == "Host":
      return header['value']

def get_hosts_from_harfile(harfile) -> set:
  hosts = set()
  for entry in harfile['log']['entries']:
    domain_name = get_domain_from_entry(entry)
    hosts.add(domain_name)

  return hosts

def get_times_from_harfile(harfile) -> "dict[str, datetime]":
  request_times = {}
  for entry in harfile['log']['entries']:
    domain_name = get_domain_from_entry(entry)
    request_time = entry['startedDateTime']
    parsed_request_time = datetime.strptime(request_time, "%Y-%m-%dT%H:%M:%S.%f%z")

    request_times[domain_name] = parsed_request_time
  
  return request_times

def get_sizes_from_harfile(harfile) -> "dict[str, int]":
  response_sizes = defaultdict(int)
  for entry in harfile['log']['entries']:
    domain_name = get_domain_from_entry(entry)
    response_size = 0
    try:
      response_size = int(entry['response']['content']['size'])
    except KeyError:
      pass

    response_sizes[domain_name] += response_size
  
  return response_sizes

 
# For each domain name in the set, run a DNS query to get the IP.
# We only take the first A record because some queries return
# 10+ different IPs for load balancing/round robin purposes
# which are all generally located in the same datacenter.
def do_dns_query(hostnames: set):
  res = {}

  for host in hostnames:
    try:
      res[host] = dns.resolver.resolve(host, 'A')[0].address
    except Exception:
      print("error: got exception when making DNS request")

  return res


@lru_cache(maxsize = None)
def get_geolocation(ip: str):
  url = f"https://ip-db.io/api/{ip}"
  response = requests.get(url)
  if response.status_code == 200:
    parsed = response.json()
    return parsed['latitude'], parsed['longitude']
  
  elif response.status_code == 429:
    print("Requests being throttled.")
    return None, None

@lru_cache(maxsize = None)
def get_my_ip():
  url = "https://checkip.amazonaws.com/"
  response = requests.get(url)
  assert response.status_code == 200
  return response.text.strip()

def map_ips_to_geolocation(hosts):
  res = {}

  for domain, ip in tqdm(hosts.items()):
    lat, long = get_geolocation(ip)
    print(f"found {lat}, {long} for domain {domain}")
    res[domain] = [lat, long]
    sleep(1.3)

  print(res)
  return res

def get_arc_width(response_sizes, current_domain):
  max_bytes = max(response_sizes.values())
  return 0.9 + (response_sizes[current_domain] / max_bytes) * 5

def get_request_color(request_timings: "dict[str, datetime]", current_domain: str):
  last_request_timestamp = max(request_timings.values())
  first_request_timestamp = min(request_timings.values())
  overall_delta = last_request_timestamp - first_request_timestamp

  current_timestamp = request_timings[current_domain]
  current_delta = current_timestamp - first_request_timestamp 

  normalized = current_delta / overall_delta

  g = 150 * normalized
  a = 1 / (normalized + 0.01)

  return f"rgba(255, {g}, 0, {a})"


def draw_map(geolocations: dict, response_sizes: "dict[str, int]", request_timings: "dict[str, datetime]"):
  my_lat, my_long = get_geolocation(get_my_ip())

  fig = go.Figure()

  for domain, latlong_array in geolocations.items():
    lat, long = latlong_array
    # Arc
    fig.add_trace(
      go.Scattergeo(
        locationmode = 'USA-states',
        lon = [my_long, long],
        lat = [my_lat, lat],
        mode = 'lines',
        line = dict(
          width = get_arc_width(response_sizes, domain),
          color = get_request_color(request_timings, domain)
        ),
        opacity = 1,
      )
    )


    # Endpoint
    fig.add_trace(go.Scattergeo(
      locationmode = 'USA-states',
      lon = [long],
      lat = [lat],
      hoverinfo = 'text',
      text = f"Domain {domain} transferred {response_sizes[domain]} bytes",
      mode = 'markers',
      marker = dict(
          size = 10,
          color = get_request_color(request_timings, domain),
          line = dict(
              width = 3,
              color = get_request_color(request_timings, domain)
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


  pio.write_html(fig, './images/test2.html')
  # pio.write_image(fig, './images/test.png', format='png', scale=6, width=1080, height=1080)

  pass

#Order access_times
def order_access_times(access_times):
  i = 1
  z = 0 #normalize vaues from zero to ones by the access times
  ord_access_times = {}
  for domain in access_times:
    if access_times[domain] == z:
      ord_access_times[domain] = i # if it has the same acceess value, z will remain the same
    else:
      z = access_times[domain]
      ord_access_times[domain] = i
      i += 1
  return ord_access_times

def main():
  args = handle_cli_args()
  harfile = parse_har_file(args.filename)
  hostnames = get_hosts_from_harfile(harfile)
  hosts_with_addrs = do_dns_query(hostnames)
  geolocations = map_ips_to_geolocation(hosts_with_addrs)

  response_sizes = get_sizes_from_harfile(harfile)
  request_timings = get_times_from_harfile(harfile)


  draw_map(geolocations, response_sizes, request_timings)

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
