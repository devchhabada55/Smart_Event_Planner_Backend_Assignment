import os
from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
from datetime import datetime, timedelta
from pymongo import MongoClient

from services.weather_service import WeatherService, WeatherAPIError, InvalidLocationError, RateLimitExceededError, OpenWeatherMapDownError
from services.event_service import EventService, Event

app = Flask(__name__)
CORS(app) # Enable CORS for all origins

# MongoDB Connection
MONGO_URI = "key"
client = MongoClient(MONGO_URI)
db = client.event_planner_db # You can choose your database name

# Initialize services with MongoDB database
OPENWEATHERMAP_BASE_URL = "http://api.openweathermap.org/data/2.5/"
OPENWEATHER_API_KEY = "api"
weather_service = WeatherService(OPENWEATHER_API_KEY, OPENWEATHERMAP_BASE_URL, db)
event_service = EventService(weather_service, db)

@app.route("/")
def home():
    return "Smart Event Planner Backend is running!"

# Event Management
@app.route("/events", methods=["POST"])
def create_event():
    data = request.get_json()
    if not data or not all(key in data for key in ["name", "location", "date", "event_type"]):
        return jsonify({"error": "Missing event details"}), 400

    try:
        event_dict = event_service.create_event(data["name"], data["location"], data["date"], data["event_type"])
        return jsonify({
            "message": "Event created successfully",
            "event_id": event_dict["event_id"],
            "event": event_dict
        }), 201
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500 # Generic weather API error
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events", methods=["GET"])
def list_events():
    events_list = []
    for event_dict in event_service.get_all_events():
        events_list.append(event_dict)
    return jsonify(events_list), 200

@app.route("/events/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    data = request.get_json()
    try:
        event_dict = event_service.update_event(event_id,
                                           name=data.get("name"),
                                           location=data.get("location"),
                                           date_str=data.get("date"),
                                           event_type=data.get("event_type"))
        if not event_dict:
            return jsonify({"error": "Event not found"}), 404

        return jsonify({
            "message": "Event updated successfully",
            "event": event_dict
        }), 200
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# Weather Integration
@app.route("/weather/<location>/<date>", methods=["GET"])
def get_weather_for_location_date(location, date):
    try:
        weather_data = weather_service.get_weather_data(location, date)
        if weather_data:
            return jsonify({"location": location, "date": date, "weather": weather_data}), 200
        else:
            return jsonify({"error": "Could not retrieve weather data for the specified location and date (e.g., date out of forecast range)."}), 404
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/weather/<location>/<date>/hourly", methods=["GET"])
def get_hourly_weather_for_location_date(location, date):
    try:
        hourly_data, error = weather_service.get_hourly_forecast(location, date)
        if hourly_data:
            return jsonify({"location": location, "date": date, "hourly_forecast": hourly_data}), 200
        elif error:
            return jsonify(error), 400 # Return specific error from service if date out of range etc.
        else:
            return jsonify({"error": "Could not retrieve hourly weather data for the specified location and date."}), 404
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/weather/<location>/<date>/historical", methods=["GET"])
def get_historical_weather_for_location_date(location, date):
    try:
        historical_data, error = weather_service.get_historical_weather(location, date)
        if historical_data:
            return jsonify({"location": location, "date": date, "historical_weather": historical_data}), 200
        elif error:
            # The get_historical_weather method already returns an error dictionary with status_code
            return jsonify({"error": error.get("error", "An unknown error occurred.")}), error.get("status_code", 500)
        else:
            return jsonify({"error": "Could not retrieve historical weather data for the specified location and date."}), 404
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events/<int:event_id>/weather-check", methods=["POST"])
def analyze_event_weather(event_id):
    try:
        event_dict = event_service.analyze_event_weather(event_id)
        if not event_dict:
            return jsonify({"error": "Event not found or weather data not available for analysis."}), 404

        return jsonify({
            "message": "Weather analyzed and updated for event",
            "event_id": event_dict["event_id"],
            "suitability": event_dict["suitability_score"],
            "weather_data": event_dict["weather_data"]
        }), 200
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events/<int:event_id>/suitability", methods=["GET"])
def get_event_suitability(event_id):
    suitability = event_service.get_event_suitability(event_id)
    if suitability:
        event_dict = event_service.get_event(event_id)
        return jsonify({
            "event_id": event_dict["event_id"],
            "location": event_dict["location"],
            "date": event_dict["date"],
            "suitability": suitability
        }), 200
    else:
        return jsonify({"message": "Weather suitability not yet calculated or available for this event.", "event_id": event_id}), 404

@app.route("/events/<int:event_id>/alternatives", methods=["GET"])
def get_alternative_dates(event_id):
    try:
        alternatives = event_service.get_alternative_dates(event_id)
        if alternatives is None: # Event not found
            return jsonify({"error": "Event not found"}), 404

        if alternatives:
            event_dict = event_service.get_event(event_id)
            return jsonify({
                "event_id": event_id,
                "original_date": event_dict["date"],
                "alternatives": alternatives
            }), 200
        else:
            return jsonify({"message": "No suitable alternative dates found within the range.", "event_id": event_id}), 200
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events/<int:event_id>/weather-trends", methods=["GET"])
def get_event_weather_trends(event_id):
    try:
        trends_data, error = event_service.get_weather_trends(event_id)
        if trends_data:
            return jsonify(trends_data), 200
        elif error:
            return jsonify(error), error.get("status_code", 500)
        else:
            return jsonify({"error": "Could not retrieve weather trends for the specified event."}), 404
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/weather/compare-locations", methods=["POST"])
def compare_locations_weather():
    data = request.get_json()
    locations = data.get("locations")
    target_date = data.get("date")
    event_type = data.get("event_type")

    if not all([locations, target_date, event_type]):
        return jsonify({"error": "Missing locations, date, or event_type"}), 400
    
    try:
        results, error = event_service.compare_weather_across_locations(locations, target_date, event_type)
        if results:
            return jsonify(results), 200
        elif error:
            return jsonify(error), error.get("status_code", 500)
        else:
            return jsonify({"message": "No comparison data available."}), 404
    except InvalidLocationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except RateLimitExceededError as e:
        return jsonify({"error": str(e)}), e.status_code
    except OpenWeatherMapDownError as e:
        return jsonify({"error": str(e)}), e.status_code
    except WeatherAPIError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events/<int:event_id>/weather-change-alert", methods=["GET"])
def get_weather_change_alert(event_id):
    try:
        alert_status = event_service.check_for_significant_weather_change(event_id)
        if alert_status.get("status") == "alert":
            return jsonify(alert_status), 200
        elif alert_status.get("status") == "no_change":
            return jsonify(alert_status), 200
        elif alert_status.get("status") == "no_previous_data":
            return jsonify(alert_status), 200
        elif alert_status.get("status") == "no_data":
            return jsonify(alert_status), 404 # No current forecast
        else:
            return jsonify(alert_status), 500 # General error from service

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/events/<int:event_id>/reminder-summary", methods=["GET"])
def get_event_reminder_summary(event_id):
    try:
        summary_data = event_service.generate_event_reminder_summary(event_id)
        if summary_data.get("status") == "success":
            return jsonify(summary_data), 200
        elif summary_data.get("status") == "no_data":
            return jsonify(summary_data), 404 # No weather data for reminder
        else:
            return jsonify(summary_data), 500 # General error from service

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0") 