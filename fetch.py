
import logging
import requests
import datetime

logger = logging.getLogger(__name__)

class Api_Data:
    def __init__(self, coordinate):
        self.co = coordinate
        logger.info(f"Initialized Api_Data with coordinates: {self.co}")

    def air_index(self):
        try:
            logger.info("Fetching air quality data...")
            ENDPOINT = 'https://api.openaq.org/v1/latest'
            parameters = {
                'coordinates': f'{self.co[0]},{self.co[1]}',
                'radius': '10000',
                'parameter': 'pm25',
            }
            response = requests.get(ENDPOINT, params=parameters, timeout=5)
            response.raise_for_status()
            data = response.json()['results'][0]['measurements'][0]['value']
            unit = response.json()['results'][0]['measurements'][0]['unit']
            logger.info(f"Air quality data received: {data} {unit}")
            return f'The air quality index is {data} {unit}'
        except Exception as e:
            logger.error(f"Error fetching air quality: {e}")
            return "Air quality data unavailable"

    def is_holiday(self):
        try:
            logger.info("Checking holiday status...")
            year = datetime.datetime.now().year
            ENDPOINT = 'https://calendarific.com/api/v2/holidays'
            parameters = {
                'api_key': '2e72745fd6562bd393296f14baacf18f92b08b3a',
                'country': 'US',
                'year': year,
            }
            response = requests.get(ENDPOINT, params=parameters, timeout=5)
            response.raise_for_status()
            holidays = response.json()['response']['holidays']
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            for holiday in holidays:
                if holiday['date']['iso'] == today:
                    logger.info("Today is a holiday")
                    return True
            logger.info("Today is not a holiday")
            return False
        except Exception as e:
            logger.error(f"Error checking holiday status: {e}")
            return False

    def is_weekend(self):
        try:
            today = datetime.datetime.now().strftime('%A')
            is_weekend = today in ['Saturday', 'Sunday']
            logger.info(f"Today is {today}, weekend: {is_weekend}")
            return is_weekend
        except Exception as e:
            logger.error(f"Error checking weekend status: {e}")
            return False

    def wind_direction(self):
        try:
            logger.info("Fetching wind direction...")
            ENDPOINT = 'https://api.openweathermap.org/data/2.5/weather'
            parameters = {
                'lat': self.co[0],
                'lon': self.co[1],
                'appid': '0794673555559a129540662e3029b866',
            }
            response = requests.get(ENDPOINT, params=parameters, timeout=5)
            response.raise_for_status()
            wind_direction = response.json()['wind']['deg']
            directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
            index = round(wind_direction / (360. / len(directions)))
            direction = directions[index % len(directions)]
            logger.info(f"Wind direction: {direction}")
            return direction
        except Exception as e:
            logger.error(f"Error fetching wind direction: {e}")
            return "Unknown"

    def temperature(self):
        try:
            logger.info("Fetching temperature...")
            ENDPOINT = 'https://api.openweathermap.org/data/2.5/weather'
            parameters = {
                'lat': self.co[0],
                'lon': self.co[1],
                'appid': '0794673555559a129540662e3029b866',
                'units': 'metric',
            }
            response = requests.get(ENDPOINT, params=parameters, timeout=5)
            response.raise_for_status()
            temp = response.json()['main']['temp']
            logger.info(f"Temperature: {temp}°C")
            return temp
        except Exception as e:
            logger.error(f"Error fetching temperature: {e}")
            return None

    def humidity(self):
        try:
            logger.info("Fetching humidity...")
            ENDPOINT = 'https://api.openweathermap.org/data/2.5/weather'
            parameters = {
                'lat': self.co[0],
                'lon': self.co[1],
                'appid': '0794673555559a129540662e3029b866',
                'units': 'metric',
            }
            response = requests.get(ENDPOINT, params=parameters, timeout=5)
            response.raise_for_status()
            humidity = response.json()['main']['humidity']
            logger.info(f"Humidity: {humidity}%")
            return humidity
        except Exception as e:
            logger.error(f"Error fetching humidity: {e}")
            return None