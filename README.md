# Bike parking tweepy bot app

A twitter bot app that searches for bicycle parking added to OpenStreetMap. Relies on AWS Lambda/S3, Python3, Tweepy, Flask, Zappa, and a boundary GeoJSON file.

### What you need
* AWS-CLI, Python3, pip, (pipenv is optional, but recommended)
* Geoapify [Static Maps API key](https://www.geoapify.com/static-maps-api)
* Twitter Developer [API keys and access tokens](https://developer.twitter.com/en/docs/twitter-api/getting-started/getting-access-to-the-twitter-api) for your bot account
* Working knowledge of python, AWS S3, OpenStreetMap (and its Overpass API)

### Setup
* Git clone the repo to your local system (git clone https://github.com/trivisonno/bikeparking-tweepy.git)
* Install all python dependencies using pip (pip install zappa flask shapely overpass boto3 tinydb)
* Create a zappa project with defaults (zappa init)
* Rename the foo/secrets.sample.py file to foo/secrets.py, and add your Geoapify and Twitter API keys and access tokens
* Update line 15 of the app.py with the node ID from which you wish to start tracking new bike parking items. If you set it to 0, then the app will tweet out info for every single bicycle parking item it finds. You might wish to only tweet about bicycle parking added after your launched your app, so you should update this with an appropriate nodeId. If you leave the default value (9256651107), that should only add anything after about November 17, 2021. (TODO: Update this setting code.)
* If you wish, adjust the radius (meters) on line 16 for the nearby POI search. (Default: 50)
* Create an S3 bucket, and update line 19 of the app.py file with the bucket name
* Line 33 includes the allowed bicycle parking types in an array. You can add types to this list if you want to be more flexible in reporting. (Default: ['stands', 'bollard', 'lockers']) ([See other types](https://wiki.openstreetmap.org/wiki/Key:bicycle_parking))
* Modify line 36 to include other types of nearby POIs. (Default seems to be a good balance)
* Replace the boundary.geojson file with your own desired boundary file. The default is Cleveland, Ohio. The app will use this boundary to filter the bicycle parking items.
* Update the zappa_settings.json and add lines 9-18 of the zappa_settings.sample.json file. The app is scheduled to check the OpenStreeetMap at the top of every hour from 9-6 EST.
* Launch to AWS Lambda with zappa (zappa deploy dev)

## Authors

Angelo [@Trivisonno](https://twitter.com/Trivisonno) (not a professional app developer, so forgive all oversights)

## License

This project is licensed under the Unlicense (Public Domain)- see the LICENSE file for details
