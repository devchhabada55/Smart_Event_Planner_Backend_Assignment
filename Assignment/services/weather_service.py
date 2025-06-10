import requests
from datetime import datetime, timedelta
from collections import Counter
import os

# Custom Exceptions for WeatherService
class WeatherAPIError(Exception):
    """Base exception for OpenWeatherMap API errors."""
    pass

class InvalidLocationError(WeatherAPIError):
    """Exception raised for invalid location in OpenWeatherMap API."""
    def __init__(self, message="Invalid location provided.", status_code=404):
        super().__init__(message)
        self.status_code = status_code

class RateLimitExceededError(WeatherAPIError):
    """Exception raised when OpenWeatherMap API rate limit is exceeded."""
    def __init__(self, message="OpenWeatherMap API rate limit exceeded. Please try again later.", status_code=429):
        super().__init__(message)
        self.status_code = status_code

class OpenWeatherMapDownError(WeatherAPIError):
    """Exception raised when OpenWeatherMap API is down or unreachable."""
    def __init__(self, message="OpenWeatherMap API is currently unavailable. Please try again later.", status_code=500):
        super().__init__(message)
        self.status_code = status_code

class WeatherService:
    def __init__(self, api_key, base_url, db):
        self.api_key = api_key
        self.base_url = base_url
        self.weather_cache_collection = db.weather_cache # MongoDB collection for weather cache
        self.WEATHER_CACHE_DURATION = timedelta(hours=3)

    def get_cached_weather(self, location, date):
        # Check MongoDB cache
        cached_data = self.weather_cache_collection.find_one({
            "location": location,
            "date": date.isoformat()
        })
        if cached_data and (datetime.now() - datetime.fromisoformat(cached_data["timestamp"])) < self.WEATHER_CACHE_DURATION:
            print(f"Serving weather for {location}, {date} from cache.")
            return cached_data["data"]
        return None

    def set_cached_weather(self, location, date, data):
        # Store in MongoDB cache
        self.weather_cache_collection.update_one(
            {
                "location": location,
                "date": date.isoformat()
            },
            {
                "$set": {
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }
            },
            upsert=True
        )
        print(f"Cached weather for {location}, {date}.")

    def _get_coordinates_from_location(self, location):
        geocoding_url = "https://api.openweathermap.org/geo/1.0/direct"
        params = {
            'q': location,
            'limit': 1, # Get only the top result
            'appid': self.api_key
        }
        try:
            response = requests.get(geocoding_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data:
                return data[0]['lat'], data[0]['lon']
            else:
                raise InvalidLocationError(f"Could not find coordinates for location: {location}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching coordinates for {location}: {e}")
            raise OpenWeatherMapDownError(f"Failed to connect to Geocoding API: {e}")

    def _fetch_weather_from_openweathermap(self, lat, lon, date_obj):
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }

        today = datetime.now().date()
        endpoint = None

        if date_obj == today:
            endpoint = "weather"
        elif today < date_obj <= (today + timedelta(days=5)): # 5-day / 3-hour forecast
            endpoint = "forecast"
        else:
            # Dates outside current or 5-day forecast range are not supported on free tier
            print(f"Date {date_obj} is out of supported range for API 2.5.")
            return None

        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params)

            # Handle API errors specifically BEFORE raise_for_status()
            if response.status_code == 401:
                raise WeatherAPIError("Invalid OpenWeatherMap API key.")
            elif response.status_code == 404:
                # For lat/lon calls, 404 means no data for coords, or other API issue.
                raise InvalidLocationError(f"Weather data not found for coordinates: {lat}, {lon}")
            elif response.status_code == 429:
                raise RateLimitExceededError()
            
            # Raise HTTPError for other bad responses (e.g., 5xx, or other 4xx not explicitly handled)
            response.raise_for_status()
            data = response.json()

            weather_info = {}
            if endpoint == "weather": # Current weather
                weather_info = {
                    "temperature": data.get('main', {}).get('temp'),
                    "feels_like": data.get('main', {}).get('feels_like'),
                    "humidity": data.get('main', {}).get('humidity'),
                    "pressure": data.get('main', {}).get('pressure'),
                    "wind_speed": data.get('wind', {}).get('speed'),
                    "wind_deg": data.get('wind', {}).get('deg'),
                    "description": data.get('weather', [{}])[0].get('description'),
                    "main": data.get('weather', [{}])[0].get('main'),
                    "precipitation": data.get('rain', {}).get('1h', 0) or data.get('snow', {}).get('1h', 0)
                }
            elif endpoint == "forecast": # 5-day / 3-hour forecast (summarized for the day)
                daily_forecasts = []
                for item in data['list']:
                    forecast_time = datetime.fromtimestamp(item['dt'])
                    if forecast_time.date() == date_obj:
                        daily_forecasts.append(item)
                
                if daily_forecasts:
                    temps = [item['main']['temp'] for item in daily_forecasts]
                    humidities = [item['main']['humidity'] for item in daily_forecasts]
                    wind_speeds = [item['wind']['speed'] for item in daily_forecasts]
                    total_precipitation = sum(item.get('rain', {}).get('3h', 0) or item.get('snow', {}).get('3h', 0) for item in daily_forecasts)
                    
                    weather_descriptions = [item['weather'][0]['description'] for item in daily_forecasts]
                    weather_main_categories = [item['weather'][0]['main'] for item in daily_forecasts]
                    
                    dominant_description = Counter(weather_descriptions).most_common(1)[0][0]
                    dominant_main = Counter(weather_main_categories).most_common(1)[0][0]

                    weather_info = {
                        "temperature": sum(temps) / len(temps) if temps else None,
                        "temperature_min": min(temps) if temps else None,
                        "temperature_max": max(temps) if temps else None,
                        "humidity": sum(humidities) / len(humidities) if humidities else None,
                        "wind_speed": sum(wind_speeds) / len(wind_speeds) if wind_speeds else None,
                        "precipitation": total_precipitation,
                        "description": dominant_description,
                        "main": dominant_main
                    }
            
            if not weather_info:
                print(f"DEBUG: Raw API response for ({lat}, {lon}) on {date_obj}: {data}")
                print(f"No relevant weather data found in API response for ({lat}, {lon}) on {date_obj}")
                return None
            return weather_info

        except requests.exceptions.RequestException as e:
            print(f"Network or general request error fetching weather: {e}")
            raise OpenWeatherMapDownError(f"Failed to connect to OpenWeatherMap API: {e}")
        except Exception as e:
            print(f"An unexpected error occurred in _fetch_weather_from_openweathermap: {e}")
            raise WeatherAPIError(f"Error processing weather data: {e}")

    def get_hourly_forecast(self, location, date):
        # Hourly forecast is not directly available on the free tier beyond 3-hour intervals in the 5-day forecast.
        # This method will return an error indicating the limitation.
        return None, {"error": "Detailed hourly forecast is not available on the free OpenWeatherMap API tier.", "status_code": 400}

    def get_historical_weather(self, location, date):
        # Historical weather data is not available on the free OpenWeatherMap API tier.
        return None, {"error": "Historical weather data is not available on the free OpenWeatherMap API tier.", "status_code": 400}

    def get_5day_3hour_forecast(self, location):
        # This method fetches the raw 5-day / 3-hour forecast data
        try:
            lat, lon = self._get_coordinates_from_location(location) # Get coordinates
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'
            }

            url = f"{self.base_url}forecast"
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if response.status_code == 401:
                raise WeatherAPIError("Invalid OpenWeatherMap API key.")
            elif response.status_code == 404:
                raise InvalidLocationError(f"Location '{location}' not found.")
            elif response.status_code == 429:
                raise RateLimitExceededError()
            elif response.status_code >= 500:
                raise OpenWeatherMapDownError()

            if 'list' in data:
                return data['list'], None # Return the raw list of 3-hour forecasts
            else:
                return None, {"error": "No 5-day / 3-hour forecast data found.", "status_code": 404}

        except requests.exceptions.RequestException as e:
            print(f"Network or general request error fetching 5-day/3-hour forecast for {location}: {e}")
            return None, {"error": f"Failed to connect to OpenWeatherMap API for 5-day forecast: {e}", "status_code": 500}
        except Exception as e:
            print(f"An unexpected error occurred in get_5day_3hour_forecast: {e}")
            return None, {"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}

    def get_weather_data(self, location, date):
        # Ensures date is a datetime.date object when interacting with cache and _fetch_weather_from_openweathermap
        if isinstance(date, str):
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            date_obj = date

        cached_weather = self.get_cached_weather(location, date_obj)
        if cached_weather:
            print(f"Serving weather for {location}, {date_obj} from cache.")
            return cached_weather
        
        print(f"Fetching weather for {location}, {date_obj} from OpenWeatherMap.")
        try:
            lat, lon = self._get_coordinates_from_location(location) # Get coordinates
            weather_data = self._fetch_weather_from_openweathermap(lat, lon, date_obj) # Pass lat, lon
            if weather_data:
                self.set_cached_weather(location, date_obj, weather_data)
            return weather_data
        except WeatherAPIError as e:
            raise e
        except Exception as e:
            print(f"An unexpected error occurred while fetching weather for {location}, {date_obj}: {e}")
            raise WeatherAPIError(f"Could not retrieve weather data: {e}") 