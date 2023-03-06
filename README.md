# PyOSMRenderer
 [![Aveygo - PyOSMRenderer](https://img.shields.io/static/v1?label=Aveygo&message=PyOSMRenderer&color=black&logo=github)](https://github.com/Aveygo/PyOSMRenderer "Go to GitHub repo")
[![stars - PyOSMRenderer](https://img.shields.io/github/stars/Aveygo/PyOSMRenderer?style=social)](https://github.com/Aveygo/PyOSMRenderer)[![Python 3.9.9](https://img.shields.io/badge/python-3.9.9-black.svg)](https://www.python.org/downloads/release/python-399/)

A minimal self hosted tile explorer for osm data. 

<p align="center">
  <img src="https://raw.githubusercontent.com/Aveygo/PyOSMRenderer/main/sydney_sample.png">
</p>

## Steps to run

0. Download python/pip and run 
```
pip3 install osmium Pillow numpy 
```
1. Download project files [here](https://github.com/Aveygo/PyOSMRenderer/archive/refs/heads/main.zip)
2. Download your osm data from https://download.geofabrik.de/ (anything .osm.pbf) and place in root folder next to build_database.py
3. Build the database
```
python3 build_database.py <the .osm.pbf file>
```
4. Run the server
```
python3 api.py
```
5. Open the browser and go to http://localhost:8000

### Emphasis on the minimal

This is a very bare bones approach to the task of mapping and was meant for dipping my toes into rtrees, cairo, caching, and other performance guides.
I highly recommended [osmnx](https://github.com/gboeing/osmnx) for a more fleshed out project.
The sydney_sample.png was rendered with tile resolution=1024 and query_limit=10000 for a more detailed result.
