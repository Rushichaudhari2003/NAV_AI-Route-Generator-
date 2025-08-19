
import folium
import requests
from flask import Flask, render_template, request
import openrouteservice
import time
import random
import math
from requests.exceptions import RequestException
from fetch import Api_Data

app = Flask(__name__, template_folder='templates')

# Configuration
TOMTOM_API_KEY = 'z0W6OG7ABkPUfzncQSvRo8RYjuu3U1IX'
OPENROUTE_API_KEY = '5b3ce3597851110001cf6248ba033b0437064cbe8ce851752bc3eb94'
REQUEST_TIMEOUT = 5
MAX_TRAFFIC_POINTS = 20

# Traffic colors
TRAFFIC_COLORS = {
    0.0: '#FF0000',  # Red
    0.5: '#FFA500',  # Orange
    0.8: '#00FF00',  # Green
    1.0: '#0000FF'   # Blue
}

def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

def get_traffic_color(speed_ratio):
    for threshold, color in sorted(TRAFFIC_COLORS.items()):
        if speed_ratio <= threshold:
            return color
    return TRAFFIC_COLORS[1.0]

def generate_simulated_traffic(route_coords):
    """Generate realistic simulated traffic data"""
    traffic_data = []
    for i, point in enumerate(route_coords):
        lng, lat = point[0], point[1]
        progress = i / len(route_coords)
        hour = time.localtime().tm_hour
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            base_speed = random.uniform(0.3, 0.7)
        else:
            base_speed = random.uniform(0.6, 1.0)
        if random.random() < 0.1:  # 10% chance of congestion
            base_speed *= random.uniform(0.3, 0.6)
        traffic_data.append({
            'lat': lat,
            'lng': lng,
            'speed_ratio': max(0.1, min(1.0, base_speed))
        })
    return traffic_data

def get_traffic_data(route_coords):
    """Try to get real traffic data, fallback to simulated"""
    try:
        sampled_points = route_coords[::max(1, len(route_coords)//MAX_TRAFFIC_POINTS)]
        traffic_data = []
        valid_points = 0
        
        for point in sampled_points:
            lng, lat = point[0], point[1]
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lng}&unit=KMPH&key={TOMTOM_API_KEY}"
            
            try:
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    if 'flowSegmentData' in data:
                        current = data['flowSegmentData'].get('currentSpeed', 50)
                        free_flow = data['flowSegmentData'].get('freeFlowSpeed', 60)
                        ratio = current / free_flow if free_flow > 0 else 0.8
                        valid_points += 1
                    else:
                        ratio = random.uniform(0.5, 0.9)
                else:
                    ratio = random.uniform(0.5, 0.9)
                    
                traffic_data.append({
                    'lat': lat,
                    'lng': lng,
                    'speed_ratio': ratio
                })
                time.sleep(0.05)
                
            except RequestException:
                traffic_data.append({
                    'lat': lat,
                    'lng': lng,
                    'speed_ratio': random.uniform(0.5, 0.9)
                })
        
        print(f"[INFO] Valid traffic points: {valid_points}/{len(traffic_data)}")
        return traffic_data if valid_points > 0 else generate_simulated_traffic(route_coords)
        
    except Exception as e:
        print(f"[WARNING] Traffic API failed: {str(e)}")
        return generate_simulated_traffic(route_coords)

def get_route(client, coords, profile, preference):
    """Safe route fetching with error handling"""
    try:
        route = client.directions(
            coordinates=coords,
            profile=profile,
            format='geojson',
            preference=preference
        )
        if 'features' in route and len(route['features']) > 0:
            return route
    except Exception as e:
        print(f"[ERROR] Route API failed ({preference}): {str(e)}")
    return None

@app.route('/', methods=['GET'])
def index():
    """Handle GET requests"""
    return render_template('index.html', map_html=None, durations=None, coordinates=None)

@app.route('/', methods=['POST'])
def get_map():
    """Handle POST requests"""
    try:
        start_time = time.time()
        
        # Get input parameters
        use_current_location = request.form.get('use_current_location') == 'true'
        
        if use_current_location:
            lat1 = float(request.form['lat1'])
            lng1 = float(request.form['lng1'])
        else:
            start_address = request.form['start_address']
            lat1, lng1 = geocode_address(start_address)
            if None in (lat1, lng1):
                return render_template('index.html', map_html=None, durations=["Invalid starting point"])
        
        destination = request.form['destination']
        vehicle_type = request.form['vehicle_type']
        
        # Initialize weather data fetcher
        weather_fetcher = Api_Data((lat1, lng1))
        temp = weather_fetcher.temperature()
        humidity = weather_fetcher.humidity()
        wind_dir = weather_fetcher.wind_direction()
        air_quality = weather_fetcher.air_index()
        
        # Geocode destination
        geocode_start = time.time()
        lat2, lng2 = geocode_address(destination)
        if None in (lat2, lng2):
            return render_template('index.html', map_html=None, durations=["Invalid destination"])
        
        print(f"[PERF] Geocoding took {time.time()-geocode_start:.2f}s")
        
        # Create base map
        m = folium.Map(location=[(lat1+lat2)/2, (lng1+lng2)/2], zoom_start=13)
        
        # Get routes
        client = openrouteservice.Client(key=OPENROUTE_API_KEY)
        coords = [[lng1, lat1], [lng2, lat2]]
        profile = 'driving-car' if vehicle_type == 'car' else 'foot-walking'
        
        # Get both route options
        routes = [
            ('Fastest', '#0000FF', get_route(client, coords, profile, 'fastest')),
            ('Shortest', '#FF00FF', get_route(client, coords, profile, 'shortest'))
        ]
        
        durations = []
        all_route_coords = []
        valid_routes = []
        
        for name, color, route in routes:
            if not route:
                continue
                
            try:
                # Process route
                duration = route['features'][0]['properties']['segments'][0]['duration']
                durations.append(f"{name}: {format_duration(duration)}")
                
                raw_coords = route['features'][0]['geometry']['coordinates']
                route_coords = [[coord[1], coord[0]] for coord in raw_coords]
                all_route_coords.append(route_coords)
                valid_routes.append((name, color, route, route_coords))
                
            except KeyError as e:
                print(f"[ERROR] Missing route data ({name}): {str(e)}")
                continue
        
        if not valid_routes:
            return render_template('index.html', map_html=None, durations=["No valid routes found"])
        
        # Add traffic and routes to map
        for name, color, route, route_coords in valid_routes:
            # Get traffic data
            traffic_start = time.time()
            traffic_data = get_traffic_data(route['features'][0]['geometry']['coordinates'])
            print(f"[PERF] Traffic data for {name} took {time.time()-traffic_start:.2f}s")
            
            # Add traffic visualization
            for i in range(len(traffic_data)-1):
                start = traffic_data[i]
                end = traffic_data[i+1]
                folium.PolyLine(
                    locations=[[start['lat'], start['lng']], [end['lat'], end['lng']]],
                    color=get_traffic_color((start['speed_ratio'] + end['speed_ratio'])/2),
                    weight=8,
                    opacity=0.8
                ).add_to(m)
            
            # Add route line
            folium.GeoJson(
                route,
                name=name,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 4,
                    'opacity': 0.7,
                    'dashArray': '5,5' if name == 'Shortest' else None
                }
            ).add_to(m)
        
        # Weather popup content
        weather_popup = f"""
        <div style="min-width: 150px">
            <h4 style="margin:0 0 5px 0">Current Weather</h4>
            <div>Temperature: {temp}°C</div>
            <div>Humidity: {humidity}%</div>
            <div>Wind: {wind_dir}</div>
            <div>{air_quality}</div>
        </div>
        """
        
        # Add markers with weather info
        folium.Marker(
            [lat1, lng1], 
            popup=weather_popup,
            icon=folium.Icon(color='green')
        ).add_to(m)
        
        # Add blue circle around current location
        folium.Circle(
            location=[lat1, lng1],
            radius=30,
            color='blue',
            fill=False,
            weight=3
        ).add_to(m)
        
        folium.Marker([lat2, lng2], popup='Destination', icon=folium.Icon(color='red')).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; z-index: 1000;
                    background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.3)">
            <h4 style="margin:0 0 5px 0">Traffic Conditions</h4>
            <div><i style="background:#FF0000; width:20px; height:10px; display:inline-block;"></i> Heavy</div>
            <div><i style="background:#FFA500; width:20px; height:10px; display:inline-block;"></i> Moderate</div>
            <div><i style="background:#00FF00; width:20px; height:10px; display:inline-block;"></i> Flowing</div>
            <div><i style="background:#0000FF; width:20px; height:10px; display:inline-block;"></i> Fast</div>
            <h4 style="margin:10px 0 5px 0">Routes</h4>
            <div><i style="background:#0000FF; width:20px; height:10px; display:inline-block;"></i> Fastest</div>
            <div><i style="background:#FF00FF; width:20px; height:10px; display:inline-block;"></i> Shortest</div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        print(f"[PERF] Total processing time: {time.time()-start_time:.2f}s")
        return render_template(
            'index.html', 
            map_html=m._repr_html_(), 
            durations=durations if durations else ["No duration info"],
            coordinates=all_route_coords if all_route_coords else None
        )
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return render_template('index.html', map_html=None, durations=["Error processing request"])

def geocode_address(address):
    try:
        url = "https://api.openrouteservice.org/geocode/search"
        params = {'api_key': OPENROUTE_API_KEY, 'text': address, 'size': 1}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            geo = response.json()
            if geo.get('features'):
                coords = geo['features'][0]['geometry']['coordinates']
                return coords[1], coords[0]  # lat, lng
    except Exception as e:
        print(f"[ERROR] Geocoding failed: {str(e)}")
    return None, None

if __name__ == '__main__':
    app.run(debug=True, threaded=True)