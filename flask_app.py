from flask import Flask, request, render_template, jsonify
import folium
from folium.plugins import MarkerCluster
import requests, math
from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote
import mysql.connector

app = Flask(__name__)

# Now you can use the `db` object to interact with your MongoDB Atlas database
def get_db_connection():
    config = {
        'user': 'jinoo2',
        'password': 'Unconcern20!',
        'host': 'jinoo2.mysql.pythonanywhere-services.com',
        'database': 'jinoo2$b2b_database_1',
    }
    return mysql.connector.connect(**config)

create_table_query = """CREATE TABLE IF NOT EXISTS coordinates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    latitude FLOAT,
    longitude FLOAT,
    name VARCHAR(255),
    info VARCHAR(255),
    last_used VARCHAR(255),
    address VARCHAR(255),
    location_point POINT
)"""

mymap = folium.Map(location=[37.5665, 126.9780], zoom_start=15, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(mymap)

def get_nearby_points(latitude, longitude, radius):
    connection = get_db_connection()
    cursor = connection.cursor()
    select_query = """
    SELECT id, latitude, longitude, name, info, last_used, address FROM coordinates
    WHERE ST_Distance(location_point, ST_PointFromText('POINT(%s %s)')) <= %s
    ORDER BY last_used DESC
    """

    cursor.execute(select_query, (longitude, latitude, float(radius)))
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result

def insert_coordinates_if_not_exist(coordinates):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    for coord in coordinates:
        location = (float(coord[0]), float(coord[1]), coord[2], coord[3], coord[4], coord[5])
        # Check if the location already exists in the database
        find_location_query = "SELECT * FROM coordinates WHERE latitude=%s AND longitude=%s"
        cursor.execute(find_location_query, (location[0], location[1]))
        result = cursor.fetchall()
        
        if not result:
            insert_location_query = """INSERT INTO coordinates 
                (latitude, longitude, name, info, last_used, address, location_point) 
                VALUES (%s, %s, %s, %s, %s, %s, ST_PointFromText(%s))"""
            cursor.execute(insert_location_query, (location[0], location[1], location[2], location[3], location[4], location[5], f"POINT({location[0]} {location[1]})"))
            connection.commit()
    cursor.close()
    connection.close()

@app.route('/store/<int:store_id>')
def store_details(store_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    select_query = """
    SELECT latitude, longitude, name, info, last_used, address FROM coordinates
    WHERE id = %s
    """

    cursor.execute(select_query, (store_id,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return jsonify({'latitude': result[0], 'longitude': result[1], 'name': result[2], 'info': result[3], 'last_used': result[4], 'address': result[5]})

@app.route('/')
def mapview():
    mymap = folium.Map(location=[37.5665, 126.9780], zoom_start=15, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster().add_to(mymap)

    if request.method == 'POST':
        address = request.form.get('address')
        # Search for the entered address
        naver_client_id = '0qv1pkl5kk'
        naver_client_secret = 'hpMQX1tKwTNJky9heiT4sxYVmJZ6SW1FgU232uUI'
        headers = {'X-NCP-APIGW-API-KEY-ID': naver_client_id, 'X-NCP-APIGW-API-KEY': naver_client_secret}
        url = f'https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query={address}'
        response = requests.get(url, headers=headers)
        print('url:', url)
        print('headers:' , headers)
        if response.status_code == 200:
            location = response.json()['addresses'][0]
            lat = float(location['y'])
            lng = float(location['x'])
            # Change the map center to the searched address location
            mymap.location = [lat, lng]
            mymap.zoom_start = 15
            coordinates = get_nearby_points(lat, lng, 5000)
            stores_with_distance = []
            for coord in coordinates:
                store_id = coord[0]
                store_lat = coord[1]
                store_lng = coord[2]
                R = 6371  # Radius of the Earth in km
                lat1, lat2 = radians(lat), radians(store_lat)
                lng1, lng2 = radians(lng), radians(store_lng)
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
                c = 2 * asin(sqrt(a))
                distance = round(R * c, 2)
                stores_with_distance.append((store_lat, store_lng, distance, coord[3], coord[4], coord[5], coord[6]))
            # Sort the stores by distance
            stores_with_distance.sort(key=lambda x: x[2])
            # Show the information of the nearest store
            nearest_store = stores_with_distance[0]
            popup_html = f'<strong>{nearest_store[3]}</strong><p><strong>Address:</strong> {nearest_store[6]}<br><strong>Info:</strong> {nearest_store[4]}<br><strong>Last used:</strong> {nearest_store[5]}</p>'
            folium.Marker(location=[nearest_store[0], nearest_store[1]], icon=folium.Icon(icon='star',color='red'), popup=folium.Popup(popup_html, max_width=250, max_height=100)).add_to(mymap)
            line_coords = [(lat, lng), (nearest_store[0], nearest_store[1])]
            folium.PolyLine(locations=line_coords, color='red').add_to(mymap)
        else:
            print('Error: Unable to geocode address.')
    else:
        coordinates = get_nearby_points(37.5665, 126.9780, 5000)
        for coord in coordinates:
            store_id = coord[0]
            latitude = coord[1]
            longitude = coord[2]
            name = coord[3]
            info = coord[4]
            last_used = coord[5]
            address = coord[6]
            popup_html = f'<strong>{name}</strong><p><strong>Address:</strong> {address}<br><strong>Info:</strong> {info}<br><strong>Last used:</strong> {last_used}</p>'
            marker = folium.Marker(location=(float(latitude), float(longitude)), popup=folium.Popup(popup_html, max_width=250, max_height=100))
            marker.add_to(marker_cluster)


    return render_template('index.html', mymap=mymap._repr_html_())

@app.route('/search', methods=['POST'])
def search_address():
    mymap = folium.Map(location=[37.5665, 126.9780], zoom_start=15, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster().add_to(mymap)

    if request.method == 'POST':
        address = request.form.get('address')
        # Search for the entered address
        naver_client_id = '0qv1pkl5kk'
        naver_client_secret = 'hpMQX1tKwTNJky9heiT4sxYVmJZ6SW1FgU232uUI'
        headers = {'X-NCP-APIGW-API-KEY-ID': naver_client_id, 'X-NCP-APIGW-API-KEY': naver_client_secret}
        url = f'https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query={address}'
        response = requests.get(url, headers=headers)
        print('url:', url)
        print('headers:' , headers)
        if response.status_code == 200:
            location = response.json()['addresses'][0]
            lat = float(location['y'])
            lng = float(location['x'])
            # Change the map center to the searched address location
            mymap.location = [lat, lng]
            mymap.zoom_start = 15
            folium.Marker(
                location=[lat, lng],
                popup='Searched Address',
                icon=folium.Icon(color='blue')
            ).add_to(mymap)
            coordinates = get_nearby_points(lat, lng, 5000)
            stores_with_distance = []
            for coord in coordinates:
                store_id = coord[0]
                store_lat = coord[1]
                store_lng = coord[2]
                R = 6371  # Radius of the Earth in km
                lat1, lat2 = radians(lat), radians(store_lat)
                lng1, lng2 = radians(lng), radians(store_lng)
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
                c = 2 * asin(sqrt(a))
                distance = round(R * c, 2)
                stores_with_distance.append((store_lat, store_lng, distance, coord[3], coord[4], coord[5], coord[6]))
            # Sort the stores by distance
            stores_with_distance.sort(key=lambda x: x[2])

            # Show the information of the nearest store
            nearest_store = stores_with_distance[0]
            popup_html = f'<strong>{nearest_store[3]}</strong><p><strong>Address:</strong> {nearest_store[6]}<br><strong>Info:</strong> {nearest_store[4]}<br><strong>Last used:</strong> {nearest_store[5]}<br><strong>Distance:</strong> {nearest_store[2]} km</p>'
            marker = folium.Marker(location=[nearest_store[0], nearest_store[1]], icon=folium.Icon(icon='star', color='red'), popup=folium.Popup(popup_html, max_width=250, max_height=100))
            marker.add_to(marker_cluster)
            line_coords = [(lat, lng), (nearest_store[0], nearest_store[1])]
            folium.PolyLine(locations=line_coords, color='red').add_to(mymap)
            all_coordinates = get_nearby_points(37.5665, 126.9780, 5000)
        for coord in all_coordinates:
            store_id = coord[0]
            latitude = coord[1]
            longitude = coord[2]
            name = coord[3]
            info = coord[4]
            last_used = coord[5]
            address = coord[6]

            if latitude == nearest_store[0] and longitude == nearest_store[1]:
                icon_color = 'red'
                icon_name = 'star'
            else:
                icon_color = 'blue'
                icon_name = 'circle'

            popup_html = f'<strong>{name}</strong><p><strong>Address:</strong> {address}<br><strong>Info:</strong> {info}<br><strong>Last used:</strong> {last_used}</p>'
            marker = folium.Marker(location=(float(latitude), float(longitude)), icon=folium.Icon(icon=icon_name, color=icon_color), popup=folium.Popup(popup_html, max_width=250, max_height=100))
            marker.add_to(marker_cluster)
        else:
            print('Error: Unable to geocode address.')
    else:
        coordinates = get_nearby_points(37.5665, 126.9780, 5000)
        for coord in coordinates:
            store_id = coord[0]
            latitude = coord[1]
            longitude = coord[2]
            name = coord[3]
            info = coord[4]
            last_used = coord[5]
            address = coord[6]
            popup_html = f'<strong>{name}</strong><p><strong>Address:</strong> {address}<br><strong>Info:</strong> {info}<br><strong>Last used:</strong> {last_used}</p>'
            marker = folium.Marker(location=(float(latitude), float(longitude)), popup=folium.Popup(popup_html, max_width=250, max_height=100))
            marker.add_to(marker_cluster)
            
    return render_template('index.html', mymap=mymap._repr_html_())


if __name__ == '__main__':
    app.run(debug=True)