import overpass # https://github.com/mvexel/overpass-api-python-wrapper
from shapely.geometry import mapping, shape, Point, Polygon
import json
import urllib
import tweepy
from flask import Flask
from flask import render_template
import boto3
from tinydb import TinyDB, Query
from foo.secrets import *

app = Flask(__name__)

api = overpass.API()
afterNodeNumber = 9256651107 # Restricts to items newer than ~ Nov. 15, 2021; Set to zero if you want to tweet everything
nearbyRadius = 50 # Search radius for POIs near bike parking

s3 = boto3.client('s3')
s3bucket = 'bikeparking'
try:
    s3.download_file(s3bucket, 'db.json', '/tmp/db.json')
except:
    pass
db = TinyDB('/tmp/db.json')
Node = Query()

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
apiTwitter = tweepy.API(auth)

# App will only tweet about these bike parking type values
# https://wiki.openstreetmap.org/wiki/Key:bicycle_parking
allowableBikeParkingTypes = ['stands', 'bollard', 'lockers']

# App will search for nearby POIs with only these keys
typesNearby = ['building', 'amenity', 'shop', 'leisure', 'name']


def getStaticMap(lat, lng):
    url = 'https://maps.geoapify.com/v1/staticmap?style=osm-carto&width=660&height=330&center=lonlat:'+lng+','+lat+'&zoom=16&marker=lonlat:'+lng+','+lat+';color:%23ff0000;size:medium&apiKey='+apikey
    urllib.request.urlretrieve(url, '/tmp/'+lat+','+lng+'.jpg')


def getNearbyPlacesOSM(lat, lng):

    # overpass-turbo query
    query = '''
    [out:json][timeout:25];
// gather results
(
  node["shop"]({{bbox}});
  way["shop"]({{bbox}});
  node["amenity"]({{bbox}});
  node["name"]({{bbox}});
  way["name"]({{bbox}});
  way["leisure"]({{bbox}});
);
// print results
out body;
>;
'''


    # Build the OSM overpass query to find POIs within <radius> meters
    queryArray = []
    for itemType in typesNearby:
        queryArray.append('node['+itemType+'](around:'+str(nearbyRadius)+','+lat+','+lng+');way['+itemType+'](around:'+str(nearbyRadius)+','+lat+','+lng+');')
    query = '(' + ('').join(queryArray) + ');out body;>;'
    print(query)
    # query = '(node["shop"](around:'+radius+','+lat+','+lng+');way["shop"](around:'+radius+','+lat+','+lng+');node["amenity"](around:'+radius+','+lat+','+lng+');node["name"](around:'+radius+','+lat+','+lng+');way["name"](around:'+radius+','+lat+','+lng+');way["leisure"](around:'+radius+','+lat+','+lng+');way["building"](around:'+radius+','+lat+','+lng+'););out body;>;'
    # print(query)
    response = api.get(query, responseformat="geojson")

    places = []
    for item in response['features']:
        if "name" in item['properties'].keys():
            for type in typesNearby:
                if type in item['properties'].keys():
                    places.append(item['properties']['name'])
                    break
    places = sorted(places) # Sort the places array alphabetically
    return places

def main(bike_data):
    lat, lng = bike_data['geometry']['coordinates'][1], bike_data['geometry']['coordinates'][0]

    # App will only tweet about these bike parking type values
    if bike_data['properties']['bicycle_parking'] not in allowableBikeParkingTypes:
        print('Unacceptable bike rack type for', "https://www.openstreetmap.org/node/"+str(bike_data['id']))
    else:

        #Check if already in the database
        if len(db.search(Node.nodeId == bike_data['id'])) == 0:

            # Build the tweet text
            tweet = ''

            if bike_data['properties']['capacity']:
                if int(bike_data['properties']['capacity']) == 1:
                    tweet += 'Secure parking added for '+bike_data['properties']['capacity']+" bicycle"
                else:
                    tweet += 'Secure parking added for '+bike_data['properties']['capacity']+" bicycles"
            else:
                return # REQUIRE PARKING CAPACITY

            places = getNearbyPlacesOSM(str(lat),str(lng)) #

            if len(places) > 0:
                tweet += " near " + (", ".join(places[:-2] + [" and ".join(places[-2:])]))
            tweet += "."
            if len(tweet) > 256:
                tweet = tweet[0:252] + "..."

            tweetStatus = tweet + " https://www.openstreetmap.org/node/"+str(bike_data['id'])

            # Download the static map of the bike parking location
            getStaticMap(str(bike_data['geometry']['coordinates'][1]),str(bike_data['geometry']['coordinates'][0]))
            print(tweetStatus)
            print(len(tweet),'chars')

            # Upload the image and alt-text to twitter, and then tweet the status
            media = apiTwitter.media_upload("/tmp/"+str(bike_data['geometry']['coordinates'][1])+','+str(bike_data['geometry']['coordinates'][0])+".jpg")
            mediaAltText = apiTwitter.create_media_metadata(media.media_id, 'Map image of bicycle parking location')
            tweetId = apiTwitter.update_status(tweetStatus, media_ids=[media.media_id])

            # Add the tweeted item to the TinyDb file
            db.upsert({'nodeId': bike_data['id'], 'tweet': tweetStatus, 'tweetId': json.dumps(tweetId)['id']}, Node.nodeId == bike_data['id'])


def checkBikeParking():
    print('checking for bike parking updates...')

    # Open the boundary geojson file, and generate a bounding box for the OSM POI search
    with open('boundary.geojson', 'r') as f:
        boundary_data = json.loads(f.read())['features'][0]
    boundary = Polygon(boundary_data['geometry']['coordinates'][0])
    boundary_bbox = '(' + str(boundary.bounds[1]) + ',' + str(boundary.bounds[0]) + ',' + str(boundary.bounds[3]) + ',' + str(boundary.bounds[2]) + ')'

    # Query OSM for all bicycle parking within the bounding box
    response = api.get('node["amenity"="bicycle_parking"]'+boundary_bbox+';out;', responseformat="geojson")



    for item in response['features']:
        itemPt = Point(item['geometry']['coordinates'])
        # Check if the bicycle parking item is newer than the setpoint and if it's within the boundary polygon
        if int(item['id'])>afterNodeNumber and boundary.contains(itemPt):
            if 'bicycle_parking' in item['properties'].keys():
                main(item)

    # Complete with uploading the TinyDb file to our S3 bucket
    with open('/tmp/db.json', "rb") as f:
        s3.upload_fileobj(f, s3bucket, 'db.json')


# Only for zappa deployment
@app.route('/')
def home():
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}


# A control panel function to see a table of all bicycle parking
@app.route('/panel')
def panel():
    # Open the boundary geojson file, and generate a Shapely polygon and bounding box for the OSM POI search
    with open('boundary.geojson', 'r') as f:
        boundary_data = json.loads(f.read())['features'][0]
    boundary = Polygon(boundary_data['geometry']['coordinates'][0])
    boundary_bbox = '(' + str(boundary.bounds[1]) + ',' + str(boundary.bounds[0]) + ',' + str(boundary.bounds[3]) + ',' + str(boundary.bounds[2]) + ')'

    api = overpass.API()
    response = api.get('node["amenity"="bicycle_parking"]'+boundary_bbox+';', responseformat="geojson")

    # An array holding all of the bicycle parking results
    results = []
    for feature in response['features']:
        try:
            results.append(feature)
        except:
            print(feature)

    # Render the data in the jinja template and display to user
    return render_template('panel.html', results=results, apikey=apikey)


if __name__ == "__main__":
    checkBikeParking()
