import argparse
from time import sleep
import requests
from collections import defaultdict
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

def map_ips_to_geolocation(hosts):
  res = defaultdict(lambda: [])

  for domain, ips in hosts.items():
    for ip in ips:
      lat, long = get_geolocation(ip)
      print(f"found {lat}, {long} for ip {ip}")
      res[domain].append([lat, long])
      sleep(1)

  print(res)
  return res

def draw_map(geolocations):
  pass

def main():
  args = handle_cli_args()

  harfile = parse_har_file(args.filename)

  hostnames = get_hosts_from_harfile(harfile)

  hosts_with_addrs = do_dns_query(hostnames)

  geolocations = map_ips_to_geolocation(hosts_with_addrs)

  draw_map(geolocations)

  exit(0)


if __name__ == "__main__":
  main()
