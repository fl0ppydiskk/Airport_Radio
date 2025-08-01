from flask import Flask, request, render_template
from dotenv import load_dotenv
import os
import requests
import json
import pycountry
from bs4 import BeautifulSoup
import re
from airportsdata import load
airports = load('IATA')

app = Flask(__name__)

load_dotenv()
flightradar_key = os.getenv("FLIGHTRADAR_KEY")

#Defining function
@app.route('/')
def flight_info():
    input_ = request.args.get("airport")
    output = []
    error_msg = None
    
    # List all airports with IATA codes
    airports_list = []
    for iata, data in airports.items():
        country_obj = pycountry.countries.get(alpha_2=data['country'])
        country_name = country_obj.name if country_obj else data['country']
        data["name"] = data["name"].replace('"','')
        airport_dict = {}
        airport_dict["label"] = f"{data["iata"]}, {data["name"]}, {data['city']}, {country_name}"
        airport_dict["value"] = data["iata"]
        airports_list.append(airport_dict)

    if not input_:
        return render_template("index.html", airports_list=airports_list, flight_output=output, error=None)
    
    input_ = input_.upper()
    
    if input_ not in airports:
        error_msg = f"Airport code '{input_}' not found."
        return render_template("index.html", airports_list=airports_list, flight_output=output, error=error_msg)

    # Define API URL and params
    url = "https://fr24api.flightradar24.com/api/live/flight-positions/full"

    variable_airport = airports[input_]
    variable_airport_countrycode = variable_airport["country"]
    country_obj = pycountry.countries.get(alpha_2=variable_airport_countrycode)
    variable_airport_country = country_obj.name if country_obj else variable_airport_countrycode

    bb_lat_max = variable_airport['lat'] + 1.5
    bb_lat_min = variable_airport['lat'] - 1.5
    bb_lon_min = variable_airport['lon'] - 1.5
    bb_lon_max = variable_airport['lon'] + 1.5

    params = {
        'limit': 10,
        'airports': f'outbound:{variable_airport["iata"]}',
        'categories': 'P, C',
        'bounds': f'{bb_lat_max},{bb_lat_min},{bb_lon_min},{bb_lon_max}',
        'altitude_ranges': '5-30000',
    }

    headers = {
        'Accept': 'application/json',
        'Accept-Version': 'v1',
        'Authorization': f'Bearer {flightradar_key}'
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    # Filtering and sorting most recent flights by altitude.
    sorted_flights = sorted(data["data"], key=lambda flight: (flight["alt"]))

    # Are the flights national or international?
    international_flights = []
    domestic_flights = []

    for flight in sorted_flights:
        origin = flight["orig_iata"]
        destination = flight["dest_iata"]
        origin_country = airports[origin]["country"]
        destination_country = airports[destination]["country"]

        if origin_country != destination_country:
            international_flights.append(flight)
        else:
            domestic_flights.append(flight)

    # Print error message if there are no flights
    if not international_flights and not domestic_flights:
        error_msg_no_flight = f"No recent departures at {variable_airport['name']}, {variable_airport_country}."
        return render_template("index.html", airports_list=airports_list, flight_output=output, error=error_msg_no_flight)

        ''' output.append({
            "flight": 'hello',
            "departure": f"{variable_airport['name']}, {variable_airport_country}",
            "destination": None,
            "song": None,
            "artist": None,
            "spotify_url": None,
            "message": f"No recent departures at {variable_airport['name']}, {variable_airport_country}."
        })
        
        return render_template(
            "index.html",
            airport_code=input_,
            flight_output=output,
            airports_list=airports_list
        )'''


    # International flights should be looked at first
    flights_to_process = international_flights if international_flights else domestic_flights
    flight = flights_to_process[0]

    if not international_flights:
        error_msg = ("No recent international departures. Here's the most recent national flight:")

    # Defining variables for each flight
    callsign = flight["callsign"]
    tailnumber = flight["hex"]
    origin = flight["orig_iata"]
    origin_country = airports[origin]["country"]
    destination_code = flight["dest_iata"].upper()
    destination_city = airports[destination_code]["city"]
    destination_country = airports[destination_code]["country"]
    airport_name = airports[destination_code]["name"]
    country_obj = pycountry.countries.get(alpha_2=destination_country)
    country_name = country_obj.name if country_obj else destination_country

    # Scraping the most popular song per country    
    url = f"https://kworb.net/spotify/country/{destination_country.lower()}_daily.html"
    response = requests.get(url)
    response.encoding = 'utf-8'

    artist = None
    songtitle = None
    spotify_url = None
    spotify_embed_url = None


    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"id": "spotifydaily"})
        first_row = soup.find("td", class_="np", string="1").find_parent("tr")
        links = first_row.find_all("a")
        artist = links[0].get_text(strip=True)
        songtitle = links[1].get_text(strip=True)
        spotify_href = links[1]['href']
        match = re.search(r'/track/([a-zA-Z0-9]+)\.html', spotify_href)
        spotify_id = match.group(1)
        spotify_url = f"https://open.spotify.com/track/{spotify_id}"
        spotify_embed_url = f"https://open.spotify.com/embed/track/{spotify_id}"


        output.append({
            "departure": f"{variable_airport['name']}, {variable_airport_country}",
            "flight": callsign,
            "tailnumber": tailnumber,
            "destination": f"{destination_city}, {country_name}",
            "country_name": f"{country_name}",
            "song": songtitle,
            "artist": artist,
            "spotify_url": spotify_url,
            "spotify_embed_url": f"https://open.spotify.com/embed/track/{spotify_id}",
            "message": None
        })
    else:
        # Fallback if there is no song for this country
        output.append({
            "departure": f"{variable_airport['name']}, {variable_airport_country}",
            "flight": callsign,
            "tailnumber": tailnumber,
            "destination": f"{destination_city}, {country_name}",
            "country_name": f"{country_name}",
            "song": "No song data available",
            "artist": None,
            "spotify_url": None,
            "spotify_embed_url": None,
            "message": None
        })

    return render_template(
        "index.html",
        airport_code=input_,
        flight_output=output,
        airports_list=airports_list,
        error=error_msg
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)