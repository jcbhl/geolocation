# Geolocator
This program produces a visualization of all of the HTTP requests made when loading a webpage.

## Example
![Globe demo](/assets/globe-demo.jpg)

The red requests are the ones made early in the page's loading. The thickness of the arc between the current location and the dot corresponds to the amount of data transferred to that end host.

## Running the tool
Uncompressed, our IP geolocation database is greater than Github's file storage limit. I didn't feel like setting up LFS, so it is stored as a tar archive. To fully set up the tool, you will need to run:

```bash
pip install -r requirements.txt
playwright install chromium
tar -xzf db.tar.gz db
```

Then, it can be invoked as follows:
```bash
python3 main.py https://www.cnn.com
```

which will output an HTML file in the current directory titled `geolocations-www.cnn.com.html`.
