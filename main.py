import argparse
import random
from urllib.parse import urlparse
import db_handler
from playwright.sync_api import sync_playwright
from playwright._impl._api_types import TimeoutError
import plotly.graph_objects as go
from functools import lru_cache
from datetime import datetime
import plotly.io as pio
import requests
from collections import defaultdict
from tqdm import tqdm
import dns.resolver
import json


def handle_cli_args():
    parser = argparse.ArgumentParser(
        prog="geolocator",
        description="Given a domain name, produce a map that shows all of the requests that went out during the loading of that webpage.",
    )
    parser.add_argument(
        "domain_name", help="the domain to access, for example, https://www.cnn.com"
    )
    return parser.parse_args()


def parse_har_file(filename: str):
    with open(filename) as f:
        parsed = json.load(f)

    return parsed


# Compress a full URL down to just the domain name, for example, www.cnn.com
def get_domain_from_entry(entry) -> str:
    domain = urlparse(entry["request"]["url"]).netloc
    return domain


# Collect all of the domain names from a harfile.
def get_hosts_from_harfile(harfile) -> set:
    hosts = set()
    for entry in harfile["log"]["entries"]:
        domain_name = get_domain_from_entry(entry)
        hosts.add(domain_name)

    return hosts


# Collect all of the request times from a harfile.
def get_times_from_harfile(harfile) -> "dict[str, datetime]":
    request_times = {}
    for entry in harfile["log"]["entries"]:
        domain_name = get_domain_from_entry(entry)
        request_time = entry["startedDateTime"]
        parsed_request_time = datetime.strptime(request_time, "%Y-%m-%dT%H:%M:%S.%f%z")

        request_times[domain_name] = parsed_request_time

    return request_times


# Accumulate the bytes transferred to each domain in the harfile.
def get_sizes_from_harfile(harfile) -> "dict[str, int]":
    response_sizes = defaultdict(int)
    for entry in harfile["log"]["entries"]:
        domain_name = get_domain_from_entry(entry)
        response_size = 0
        try:
            response_size = int(entry["response"]["content"]["size"])

            response_size = max(response_size, 0)
        except KeyError:
            pass

        response_sizes[domain_name] += response_size

    return response_sizes


# For each domain name in the set, run a DNS query to get the IP.
# We only take the first A record because some queries return
# 10+ different IPs for load balancing/round robin purposes
# which are all generally located at the same geolocation.
def do_dns_query(hostnames: set):
    res = {}

    print(f"Doing DNS lookups for {len(hostnames)} domains...")
    for host in hostnames:
        try:
            res[host] = dns.resolver.resolve(host, "A")[0].address
        except Exception:
            print("error: got exception when making DNS request. Continuing...")

    print(f"DNS lookups done.")

    return res


@lru_cache(maxsize=None)
def get_my_ip():
    url = "https://checkip.amazonaws.com/"
    response = requests.get(url)
    assert response.status_code == 200
    return response.text.strip()


# Use the local geolocation database to map each IP to a geolocation
def map_ips_to_geolocation(hosts):
    res = {}
    db_handler.init_db()

    print("Mapping IPs to geolocations...")
    for domain, ip in tqdm(hosts.items()):
        lat, long = db_handler.get_geolocation(ip)
        res[domain] = [lat, long]
    print("Done mapping IPs to geolocations.")

    return res


def get_arc_width(response_sizes, current_domain):
    max_bytes = max(response_sizes.values())
    return 0.9 + (response_sizes[current_domain] / max_bytes) * 5


def get_request_color(request_timings: "dict[str, datetime]", current_domain: str):
    if len(request_timings) == 1:
        return "rgba(255, 0, 0, 1)"

    last_request_timestamp = max(request_timings.values())
    first_request_timestamp = min(request_timings.values())
    overall_delta = last_request_timestamp - first_request_timestamp

    current_timestamp = request_timings[current_domain]
    current_delta = current_timestamp - first_request_timestamp

    normalized = current_delta / overall_delta

    g = 150 * normalized
    a = 1 / (normalized + 0.01)

    return f"rgba(255, {g}, 0, {a})"


# Produce the final visualization and save it to disk..
def draw_map(
    geolocations: dict,
    response_sizes: "dict[str, int]",
    request_timings: "dict[str, datetime]",
    domain_name: str,
):
    my_lat, my_long = db_handler.get_geolocation(get_my_ip())

    fig = go.Figure()

    for domain, latlong_array in geolocations.items():
        lat, long = latlong_array

        def get_noise() -> int:
            range = 0.1
            return random.uniform(-range, range)

        # To avoid many points being stacked up in the same lat/long, add some noise
        # so that we can see each request.
        end_host_long = long + get_noise()
        end_host_lat = lat + get_noise()

        # Arc
        fig.add_trace(
            go.Scattergeo(
                locationmode="USA-states",
                lon=[my_long, end_host_long],
                lat=[my_lat, end_host_lat],
                mode="lines",
                line=dict(
                    width=get_arc_width(response_sizes, domain),
                    color=get_request_color(request_timings, domain),
                ),
                opacity=1,
            )
        )

        # Endpoint
        fig.add_trace(
            go.Scattergeo(
                locationmode="USA-states",
                lon=[end_host_long],
                lat=[end_host_lat],
                hoverinfo="text",
                text=f"Domain {domain} transferred {response_sizes[domain]} bytes",
                mode="markers",
                marker=dict(
                    size=10,
                    color=get_request_color(request_timings, domain),
                    line=dict(
                        width=3, color=get_request_color(request_timings, domain)
                    ),
                ),
            )
        )

    domain = urlparse(domain_name).netloc
    fig.update_layout(
        title_text=f"Request Geolocations for {domain}",
        showlegend=False,
        geo=dict(
            showland=True,
            landcolor="rgb(243, 243, 243)",
            countrycolor="rgb(204, 204, 204)",
        ),
    )
    fig.update_geos(
        projection_type="orthographic", showcountries=True, countrycolor="Black"
    )

    filepath = f"./geolocations-{domain}.html"
    pio.write_html(fig, filepath)
    print(f"Visualization saved to {filepath}.")


# Use Playwright to grab a network capture from loading the domain.
def record_har(domain_name: str):
    domain = urlparse(domain_name).netloc
    filename = f"./trace-{domain}.har"

    with sync_playwright() as p:
        print(f"Recording network traffic for {domain_name}...")
        device = p.devices["Desktop Chrome"]
        browser = p.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(record_har_path=filename, **device)
        page = context.new_page()
        try:
            page.goto(domain_name, wait_until="networkidle")
        except TimeoutError:
            pass

        page.close()
        context.close()

        print("Recording traffic done.")

    return filename


def main():
    args = handle_cli_args()
    filename = record_har(args.domain_name)
    harfile = parse_har_file(filename)
    hostnames = get_hosts_from_harfile(harfile)
    hosts_with_addrs = do_dns_query(hostnames)
    geolocations = map_ips_to_geolocation(hosts_with_addrs)

    response_sizes = get_sizes_from_harfile(harfile)
    request_timings = get_times_from_harfile(harfile)

    draw_map(geolocations, response_sizes, request_timings, args.domain_name)

    exit(0)


if __name__ == "__main__":
    main()
