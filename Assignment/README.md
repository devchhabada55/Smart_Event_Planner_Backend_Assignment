# Smart Event Planner - Backend

## Project Description
This backend service helps users plan outdoor events by integrating with the OpenWeatherMap API to provide intelligent recommendations. It considers weather forecasts to suggest optimal event timing and locations, focusing on factors critical for outdoor event success like temperature, precipitation, and wind. The service now uses **MongoDB** for persistent storage of event and weather cache data.

## Features

### MUST HAVE Features (Core Requirements)

1.  **Single API Integration (Weather Focus)**:
    *   Integrated with OpenWeatherMap API 2.5 for current weather and 5-day/3-hour forecasts.
    *   Parses and stores weather data in your internal format.
    *   Handles API responses and errors gracefully (e.g., invalid location, API downtime, rate limits).
2.  **Event Management System**:
    *   Allows creating events with basic details (name, location, date, event type).
    *   Stores events in a **MongoDB database** with a defined schema.
    *   Links events to weather data for specified locations and dates.
3.  **Simple Weather Analysis**:
    *   Fetches weather for event location and date.
    *   Compares weather conditions against event type requirements.
    *   Provides a basic suitability score (Good/Okay/Poor) based on temperature, precipitation, and wind.
    *   Shows weather details relevant to outdoor events.
4.  **Basic Recommendation Logic**:
    *   Suggests alternative dates within the **5-day forecast range** if weather is poor, based on available API 2.5 data.
    *   Provides "better weather" alternatives for the same week.
    *   Handles cases when no good weather days are available.

### OPTIONAL Features (Extra Credit)

1.  **Enhanced Weather Analysis**:
    *   **Historical Weather**: *(Note: Not available on OpenWeatherMap API 2.5 Free tier. Will return an error indicating this limitation.)*
    *   **Hourly Breakdown**: *(Note: Not available on OpenWeatherMap API 2.5 Free tier beyond 3-hour intervals in the 5-day forecast. Will return an error indicating this limitation.)*
    *   **Weather Trends**: Analyzes improving/worsening forecasts based on the 5-day/3-hour forecast data.
    *   **Multiple Locations**: Compares weather across nearby cities.
2.  **Smart Notifications (Logic Simulation)**:
    *   **Weather Change Alerts**: Contains logic to check for significant forecast changes.
    *   **Event Reminders**: Contains logic to generate day-before weather summaries for upcoming events.
    *(Note: Actual email/SMS integration would require external services/schedulers)*
3.  **Simple Frontend Interface**:
    *   Basic HTML/CSS/JavaScript frontend (`static/index.html`) to interact with the backend.
    *   CORS enabled for frontend interaction.

## API Endpoints

The following API endpoints are available:

### Event Management
*   `POST /events`: Create a new event.
*   `GET /events`: List all stored events.
*   `PUT /events/:id`: Update details for a specific event.

### Weather Integration
*   `GET /weather/:location/:date`: Get weather for a specific location and date.
*   `POST /events/:id/weather-check`: Analyze weather for an existing event and link weather data.
*   `GET /events/:id/alternatives`: Get alternative dates with better weather for an event.
*   `GET /weather/:location/:date/hourly`: Get hourly weather forecast for a location and date. *(Note: Not available on free tier)*
*   `GET /weather/:location/:date/historical`: Get historical weather for a location and date. *(Note: Not available on free tier)*

### Simple Analytics
*   `GET /events/:id/suitability`: Get the weather suitability score for an event.
*   `GET /events/:id/weather-trends`: Get weather trends for an event.
*   `POST /weather/compare-locations`: Compare weather across multiple locations.

### Simulated Notification Endpoints
*   `GET /events/:id/weather-change-alert`: Simulate a weather change alert check for an event.
*   `GET /events/:id/reminder-summary`: Simulate generating an event reminder summary.

## Technical Challenges Addressed

*   **OpenWeatherMap API Integration**: Handled authentication, data fetching (current, 5-day/3-hour forecast for API 2.5), response parsing, and robust error handling (API downtime, invalid locations, rate limits).
*   **Internal Data Transformation**: Designed custom `Event` and `EventWeatherAnalysis` data structures.
*   **MongoDB Integration & Caching Strategy**: Implemented MongoDB for persistent storage of events and a caching strategy for weather data (3-hour duration, location-date based keys) within MongoDB.
*   **Weather Scoring Algorithm**: Developed a configurable scoring system based on event type requirements (temperature, precipitation, wind).
*   **Modular Design**: Refactored into `WeatherService` and `EventService` classes for better organization and maintainability.

## Setup Instructions

To set up and run the application, follow these steps:

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd smart-event-planner-backend
    ```

2.  **Install Dependencies:**
    Make sure you have Python (3.x recommended) and `pip` installed. Then, install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3.  **MongoDB Setup:**
    *   Ensure you have a MongoDB instance running (e.g., local installation, MongoDB Atlas cluster). This application connects to the MongoDB Atlas cluster specified in `app.py`.
    *   The connection URI for your MongoDB cluster is hardcoded in `app.py`. If you need to change it, locate the `MONGO_URI` variable and update it.

4.  **OpenWeatherMap API Key:**
    The API key for OpenWeatherMap is hardcoded in `app.py`. Locate the `OPENWEATHER_API_KEY` variable in `app.py` and replace it with your own valid API key. **Ensure your key has access to OpenWeatherMap API 2.5 features (current weather, 5-day/3-hour forecast), as detailed hourly and historical data require higher tiers.**

5.  **Run the Flask Application:**
    ```bash
    python app.py
    ```
    The application will start running on `http://127.0.0.1:5000/`.

## Testing with Postman

1.  **Import the Postman Collection:**
    You will need to import the latest Postman collection (provided in the chat history with updated dates) to test the API endpoints. This collection includes all test scenarios for event management, weather integration, and error handling, with dates adjusted to work within the OpenWeatherMap API 2.5 free-tier forecast window.
2.  **Run Tests:**
    Once the Flask application is running, you can run the requests in the Postman collection to test various functionalities.

## Using the Simple Frontend Interface

1.  **Ensure Backend is Running:**
    Make sure your Flask application is running as described in the "Run the Flask Application" section.
2.  **Open `index.html`:**
    Navigate to `http://127.0.0.1:5000/static/index.html` in your web browser. This will load the basic frontend interface, allowing you to interact with the backend to create events, fetch weather, and view recommendations. 