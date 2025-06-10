from datetime import datetime, timedelta
from .weather_service import InvalidLocationError, OpenWeatherMapDownError, RateLimitExceededError, WeatherAPIError, WeatherService

class Event:
    def __init__(self, event_id, name, location, date, event_type):
        self.event_id = event_id
        self.name = name
        self.location = location
        self.date = date  # Format: YYYY-MM-DD
        self.event_type = event_type
        self.weather_data = None  # Store last fetched weather data
        self.suitability_score = None # Store last calculated suitability score

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "name": self.name,
            "location": self.location,
            "date": self.date,
            "event_type": self.event_type,
            "weather_data": self.weather_data,
            "suitability_score": self.suitability_score
        }

    @classmethod
    def from_dict(cls, data):
        event = cls(
            event_id=data["event_id"],
            name=data["name"],
            location=data["location"],
            date=data["date"],
            event_type=data["event_type"]
        )
        event.weather_data = data.get("weather_data")
        event.suitability_score = data.get("suitability_score")
        return event

class EventWeatherAnalysis:
    def __init__(self, event_id, location, date, weather_details, suitability_score, recommendation=None):
        self.event_id = event_id
        self.location = location
        self.date = date
        self.weather_details = weather_details
        self.suitability_score = suitability_score
        self.recommendation = recommendation

class EventService:
    def __init__(self, weather_service: WeatherService, db):
        self.weather_service = weather_service
        self.events_collection = db.events # MongoDB collection for events

    def _calculate_suitability_score(self, event_type, weather_data):
        if not weather_data:
            return "Poor", 0

        score = 0
        suitability_text = "Poor"

        # Use appropriate temperature key based on whether it's current or forecast
        temp = weather_data.get("temperature_avg", weather_data.get("temperature"))
        precipitation = weather_data.get("precipitation")
        wind_speed = weather_data.get("wind_speed_avg", weather_data.get("wind_speed"))
        weather_main = weather_data.get("main")

        if event_type == "Outdoor Sports":
            if 15 <= temp <= 30:
                score += 30
            if precipitation < 20:
                score += 25
            if wind_speed < 20 / 3.6: # Convert km/h to m/s for comparison
                score += 20
            if weather_main in ["Clear", "Clouds"]:
                score += 25
                
        elif event_type == "Wedding/Formal Events":
            if 18 <= temp <= 28:
                score += 30
            if precipitation < 10:
                score += 30
            if wind_speed < 15 / 3.6:
                score += 25
            if weather_main in ["Clear", "Clouds"]:
                score += 15

        if score >= 80:
            suitability_text = "Good"
        elif score >= 50:
            suitability_text = "Okay"
        
        return suitability_text, score

    def create_event(self, name, location, date_str, event_type):
        event_id = self.events_collection.count_documents({}) + 1
        event = Event(
            event_id=event_id,
            name=name,
            location=location,
            date=date_str,
            event_type=event_type
        )
        self.events_collection.insert_one(event.to_dict())
        return event.to_dict()

    def get_event(self, event_id):
        event_data = self.events_collection.find_one({"event_id": event_id})
        if event_data:
            return Event.from_dict(event_data).to_dict()
        return None

    def update_event(self, event_id, name=None, location=None, date_str=None, event_type=None):
        event_data = self.events_collection.find_one({"event_id": event_id})
        if not event_data:
            return None

        event = Event.from_dict(event_data)

        if name: event.name = name
        if location: event.location = location
        if date_str: event.date = date_str
        if event_type: event.event_type = event_type
        
        self.events_collection.update_one(
            {"event_id": event_id},
            {"$set": event.to_dict()}
        )
        return event.to_dict()

    def get_all_events(self):
        return [Event.from_dict(event).to_dict() for event in self.events_collection.find()]

    def analyze_event_weather(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return None

        weather_data = self.weather_service.get_weather_data(event["location"], event["date"])

        if weather_data:
            event["weather_data"] = weather_data
            suitability_text, suitability_score = self._calculate_suitability_score(event["event_type"], weather_data)
            event["suitability_score"] = {"text": suitability_text, "score": suitability_score}
            return event
        else:
            event["weather_data"] = None
            event["suitability_score"] = None
            return None

    def get_event_suitability(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return None
        return event["suitability_score"]

    def get_alternative_dates(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return None

        original_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        alternatives = []

        today = datetime.now().date()
        forecast_end_date = today + timedelta(days=5)

        # Consider dates from today up to 5 days in the future for alternatives
        for i in range(0, 6): # 0 for today, up to 5 days for forecast
            alternative_date = today + timedelta(days=i)
            alternative_date_str = alternative_date.strftime("%Y-%m-%d")

            # Skip if the alternative date is the same as the original event date, unless the original is in the past.
            if alternative_date == original_date and alternative_date >= today: # Only skip if original date is not in the past
                continue

            weather_data = self.weather_service.get_weather_data(event["location"], alternative_date_str)
            if weather_data:
                suitability_text, suitability_score = self._calculate_suitability_score(event["event_type"], weather_data)
                alternatives.append({
                    "date": alternative_date_str,
                    "weather": weather_data,
                    "suitability": {"text": suitability_text, "score": suitability_score}
                })

        alternatives.sort(key=lambda x: x["suitability"]["score"], reverse=True)
        return alternatives

    def get_weather_trends(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return None, {"error": "Event not found.", "status_code": 404}

        forecast_data, error = self.weather_service.get_5day_3hour_forecast(event["location"])
        if error:
            return None, error
        if not forecast_data:
            return None, {"error": "No forecast data available for trends analysis.", "status_code": 404}

        # Group forecasts by day and calculate daily average suitability scores
        daily_suitability = {}
        for item in forecast_data:
            forecast_date_str = datetime.fromtimestamp(item['dt']).strftime("%Y-%m-%d")
            # Create a simplified weather info dictionary for scoring based on 3-hour data
            weather_info = {
                "temperature": item['main']['temp'],
                "humidity": item['main']['humidity'],
                "description": item['weather'][0]['description'] if item.get('weather') else "N/A",
                "main": item['weather'][0]['main'] if item.get('weather') else "N/A",
                "wind_speed": item['wind']['speed'],
                "precipitation": item.get('rain', {}).get('3h', 0) or item.get('snow', {}).get('3h', 0)
            }
            _, score = self._calculate_suitability_score(event["event_type"], weather_info)
            
            if forecast_date_str not in daily_suitability:
                daily_suitability[forecast_date_str] = []
            daily_suitability[forecast_date_str].append(score)
        
        # Calculate average score for each day
        average_daily_scores = {
            date: sum(scores) / len(scores) for date, scores in daily_suitability.items()
        }

        # Sort by date
        sorted_dates = sorted(average_daily_scores.keys())
        if len(sorted_dates) < 2:
            return {"trend": "Stable", "message": "Not enough data for trend analysis.", "daily_scores": average_daily_scores}, None

        # Analyze trend
        first_day_score = average_daily_scores[sorted_dates[0]]
        last_day_score = average_daily_scores[sorted_dates[-1]]

        trend = "Stable"
        message = "Weather conditions are relatively stable over the forecast period."

        if last_day_score > first_day_score + 10: # Threshold for improving
            trend = "Improving"
            message = "Weather conditions are improving over the forecast period."
        elif last_day_score < first_day_score - 10: # Threshold for worsening
            trend = "Worsening"
            message = "Weather conditions are worsening over the forecast period."
        
        return {"trend": trend, "message": message, "daily_scores": average_daily_scores}, None

    def compare_weather_across_locations(self, locations, target_date, event_type):
        results = []
        for loc in locations:
            try:
                weather_data = self.weather_service.get_weather_data(loc, target_date)
                if weather_data:
                    suitability_text, suitability_score = self._calculate_suitability_score(event_type, weather_data)
                    results.append({
                        "location": loc,
                        "date": target_date,
                        "weather": weather_data,
                        "suitability": {"text": suitability_text, "score": suitability_score}
                    })
                else:
                    results.append({"location": loc, "date": target_date, "error": "Weather data not available for the specified date range."})
            except (WeatherAPIError, InvalidLocationError, RateLimitExceededError, OpenWeatherMapDownError) as e: # type: ignore
                results.append({"location": loc, "date": target_date, "error": str(e), "status_code": e.status_code if hasattr(e, 'status_code') else 500})
            except Exception as e:
                results.append({"location": loc, "date": target_date, "error": f"An unexpected error occurred: {str(e)}", "status_code": 500})
        
        # Sort results by suitability score, with errors at the bottom
        results.sort(key=lambda x: x["suitability"]["score"] if "suitability" in x else -1, reverse=True)
        return results, None

    # Smart Notifications Logic
    def check_for_significant_weather_change(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return {"error": "Event not found."}

        current_date_obj = datetime.strptime(event["date"], '%Y-%m-%d').date()
        # For simulation, let's assume a 'previous' forecast was stored a day ago.
        # In a real system, you'd store historical forecasts for comparison.
        previous_date = current_date_obj - timedelta(days=1)

        try:
            # Fetch current forecast (for the event date)
            current_forecast = self.weather_service.get_weather_data(event["location"], current_date_obj)
            if not current_forecast:
                return {"message": "Could not retrieve current forecast for weather change check.", "status": "no_data"}

            # Simulate fetching a 'previous' forecast (e.g., from an earlier cache entry or a mock)
            # For a real system, you'd need to store historical forecasts over time.
            previous_forecast = self.weather_service.get_weather_data(event["location"], previous_date) # This will fetch or use cache if available for previous_date
            
            if not previous_forecast:
                # If no previous forecast is available, we can't determine a change.
                return {"message": f"No previous forecast available for {event['location']} on {previous_date}. Cannot determine significant change.", "status": "no_previous_data"}

            # Simplified change detection logic:
            # Check temperature change
            current_temp_day = current_forecast.get('daily_summary', {}).get('temperature', {}).get('day')
            previous_temp_day = previous_forecast.get('daily_summary', {}).get('temperature', {}).get('day')

            temp_change = None
            if current_temp_day is not None and previous_temp_day is not None:
                temp_change = abs(current_temp_day - previous_temp_day)

            # Check precipitation change (example: if precipitation appeared or disappeared)
            current_precip = current_forecast.get('daily_summary', {}).get('precipitation_description', 'none').lower()
            previous_precip = previous_forecast.get('daily_summary', {}).get('precipitation_description', 'none').lower()

            # Determine if there's a significant change based on thresholds
            significant_change = False
            change_details = []

            if temp_change and temp_change > 5: # Threshold for significant temp change in Celsius
                significant_change = True
                change_details.append(f"Temperature changed by {temp_change:.1f}°C.")

            if (('rain' in current_precip or 'snow' in current_precip) and not ('rain' in previous_precip or 'snow' in previous_precip)) or \
               ((not ('rain' in current_precip or 'snow' in current_precip)) and ('rain' in previous_precip or 'snow' in previous_precip)):
                significant_change = True
                change_details.append(f"Precipitation forecast changed from '{previous_precip}' to '{current_precip}'.")

            if significant_change:
                alert_message = f"Significant weather change detected for {event['name']} in {event['location']} on {event['date']}. " \
                                f"Details: {', '.join(change_details)}"
                return {"message": alert_message, "status": "alert", "details": change_details}
            else:
                return {"message": f"No significant weather change detected for {event['name']} in {event['location']} on {event['date']}.", "status": "no_change"}

        except (WeatherAPIError, InvalidLocationError, RateLimitExceededError, OpenWeatherMapDownError) as e:
            return {"error": f"Error checking weather change: {e}", "status": "error"}

    def generate_event_reminder_summary(self, event_id):
        event = self.get_event(event_id)
        if not event:
            return {"error": "Event not found."}

        event_date_obj = datetime.strptime(event["date"], '%Y-%m-%d').date()

        try:
            weather_data = self.weather_service.get_weather_data(event["location"], event_date_obj)

            if not weather_data:
                return {"message": "Could not retrieve weather data for event reminder.", "status": "no_data"}

            summary_parts = [
                f"Event: {event['name']}",
                f"Location: {event['location']}",
                f"Date: {event['date']}"
            ]

            daily_summary = weather_data.get('daily_summary', {})
            if daily_summary:
                summary_parts.append("--- Daily Summary ---")
                if 'temperature' in daily_summary:
                    temp = daily_summary['temperature']
                    summary_parts.append(f"Temperature: Day {temp.get('day')}°C, Night {temp.get('night')}°C")
                if 'feels_like' in daily_summary:
                    feels_like = daily_summary['feels_like']
                    summary_parts.append(f"Feels Like: Day {feels_like.get('day')}°C, Night {feels_like.get('night')}°C")
                if 'humidity' in daily_summary:
                    summary_parts.append(f"Humidity: {daily_summary['humidity']}%")
                if 'pressure' in daily_summary:
                    summary_parts.append(f"Pressure: {daily_summary['pressure']} hPa")
                if 'wind_speed' in daily_summary:
                    summary_parts.append(f"Wind Speed: {daily_summary['wind_speed']} m/s")
                if 'weather_description' in daily_summary:
                    summary_parts.append(f"Weather: {daily_summary['weather_description']}")
                if 'precipitation_description' in daily_summary:
                    summary_parts.append(f"Precipitation: {daily_summary['precipitation_description']}")

            hourly_forecast = weather_data.get('hourly_forecast', [])
            if hourly_forecast:
                summary_parts.append("--- Hourly Forecast (First 3 entries) ---")
                for i, hour_data in enumerate(hourly_forecast[:3]):
                    summary_parts.append(
                        f"  Hour {i*3}: {hour_data.get('temperature')}°C, {hour_data.get('weather_description')}"
                    )

            return {"summary": "\n".join(summary_parts), "status": "success"}

        except (WeatherAPIError, InvalidLocationError, RateLimitExceededError, OpenWeatherMapDownError) as e:
            return {"error": f"Error generating reminder summary: {e}", "status": "error"} 