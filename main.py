import argparse
from io import StringIO
import json

def handle_cli_args():
  parser = argparse.ArgumentParser(
                    prog = 'geolocator',
                    description = 'Given a HAR file exported from a browser\'s network dev tools, produce a map that shows all of the requests that went out.',
  )
  parser.add_argument('filename', required=True)
  return parser.parse_args()

def parse_har_file(filename: str):
  with open(filename) as f:
    parsed = json.load(f)
  
  return parsed

def main():
  args = handle_cli_args()

  harfile = parse_har_file(args.filename)

  print()

  

  exit(0)


if __name__ == "__main__":
  main()
