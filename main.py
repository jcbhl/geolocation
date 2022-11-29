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
            size = 2,
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
        scope = 'north america',
        projection_type = 'azimuthal equal area',
        showland = True,
        landcolor = 'rgb(243, 243, 243)',
        countrycolor = 'rgb(204, 204, 204)',
    ),
)


  pio.write_image(fig, './images/test.png', format='png', scale=6, width=1080, height=1080)

  pass

def main():
  args = handle_cli_args()
  harfile = parse_har_file(args.filename)
  hostnames = get_hosts_from_harfile(harfile)
  hosts_with_addrs = do_dns_query(hostnames)
  # geolocations = map_ips_to_geolocation(hosts_with_addrs)

  test_mapping = {
    "amplify.outbrain.com": [[37.502129, 15.08719]],
    "w.usabilla.com" : [[39.04372, -77.487488]],
    "ad.doubleclick.net": [[37.405991, -122.078514]],
    "cdn.cookielaw.org": [[37.7757, -122.395203]],
    "bea4.v.fwmrm.net": [[47.627499, -122.346199], [37, -77]],
  }

  draw_map(test_mapping)

  exit(0)


if __name__ == "__main__":
  main()
