from flask import Flask, request, jsonify, send_file, render_template_string
import google.generativeai as genai
import json
import re
import requests
import urllib.parse
import os
from dotenv import load_dotenv
from markupsafe import Markup


load_dotenv()

GOOGLE_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("MAPS_API_KEY")

app = Flask(__name__)
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-pro-exp')

HTML_TEMPLATE = '''
<form method="post" action="/get-coordinates">
    <h2>Location Prompt</h2>
    <input type="text" name="prompt" value="{{ prompt }}" 
    placeholder="Enter a location-based prompt"
    style="
        width: 600px;
        height: 50px;
        font-size: 18px;
        background-color: #e0f0ff;
        color: #003366;
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    ">

    <input type="submit" value="Generate Map">
</form>
{% if places %}
<hr>

<!-- Controls: Top right above table -->
<div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
    <div style="text-align: right;">
        <select id="themeSelector" onchange="updateMap()" style="margin-bottom: 8px;">
            <option value="default">🗺️ Default</option>
            <option value="dark">🌙 Dark</option>
            <option value="light">💡 Light</option>
            <option value="grayscale">🖤 Grayscale</option>
            <option value="retro">🧡 Retro</option>
            <option value="night">🌃 Night</option>
            <option value="aubergine">🍆 Aubergine</option>
        </select><br>
        <label>
            <input type="checkbox" id="toggleNames" checked onchange="updateMap()"> ✅ Show location names
        </label>
    </div>
</div>

<!-- Main Content: Map and Table -->
<div style="display: flex; gap: 40px; padding-top: 20px; align-items: flex-start;">
    <!-- Map Section -->
    <div style="width: 600px;">
        <h3 style="margin: 0;">Generated Map</h3>
        <img id="mapImage" src="/map.png?names=1&theme=default" alt="Map Image" style="width: 600px; height: auto; border: 1px solid #ccc; margin-top: 30px;">
    </div>

    <!-- Table Section -->
    <div style="flex: 1;">
        <h3 style="margin: 0;">Historical Facts</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="width: 100%; margin-top: 30px;">
            <tr>
                <th style="width: 30px; text-align: center;">#</th>
                <th>Location</th>
                <th>Historical Fact</th>
            </tr>
            {% for p in places %}
            <tr>
                <td style="text-align: center; font-weight: bold; background-color: {{ p.color }}; color: {{ p.text_color }};">{{ loop.index }}</td>
                <td>{{ p.name }}</td>
                <td>{{ p.fact | safe | highlight_keywords }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>

<script>
    function updateMap() {
        const showNames = document.getElementById('toggleNames').checked ? 1 : 0;
        const theme = document.getElementById('themeSelector').value;
        document.getElementById('mapImage').src = `/map.png?names=${showNames}&theme=${theme}&t=${new Date().getTime()}`;
    }
</script>
<br>
<a href="/download-json">⬇️ Download JSON</a>
{% endif %}
'''

@app.template_filter('highlight_keywords')
def highlight_keywords(text):
    keywords = [
        r"\b(\d{3,4})\b",                     # years like 1947, 1066
        r"\b(King|Queen|Emperor|Empress)\b",  # royalty
        r"\b(War|Battle|Invasion|Conquest)\b", # conflicts
        r"\b(Empire|Dynasty|Republic|Civilization)\b", # governance
        r"\b(Ancient|Medieval|Colonial|Historic)\b"  # time periods
    ]

    highlight_colors = {
        0: "#007bff",  # Blue for years
        1: "#9c27b0",  # Purple for royalty
        2: "#dc3545",  # Red for conflicts
        3: "#28a745",  # Green for governance
        4: "#fd7e14"   # Orange for time periods
    }

    for i, pattern in enumerate(keywords):
        color = highlight_colors.get(i, "#007bff")
        text = re.sub(pattern, f'<span style="color:{color}; font-weight:bold;">\\1</span>', text, flags=re.IGNORECASE)

    return Markup(text)


@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE, prompt="", places=None)

@app.route('/get-coordinates', methods=['POST'])
def get_coordinates():
    prompt = request.form.get("prompt")

    full_prompt = f"""
Extract locations from the prompt and provide JSON with:
- "name": location name
- "latitude": precise decimal coordinates
- "longitude": precise decimal coordinates  
- "fact": brief historical fact (1-2 sentences)
- "type": "country", "city", "landmark", "site", or "region"

Return raw JSON array only.
Prompt: \"\"\"{prompt}\"\"\"
"""

    try:
        response = model.generate_content(full_prompt)
        cleaned = re.sub(r"```(?:json)?|```", "", response.text).strip()
        coords = json.loads(cleaned)
        
        # Add color for each location
        marker_colors = [
            {"bg": "#ffcccc", "text": "#800000"}, # Light red
            {"bg": "#ccffcc", "text": "#004d00"}, # Light green
            {"bg": "#ccccff", "text": "#000080"}, # Light blue
            {"bg": "#ffffcc", "text": "#806600"}, # Light yellow
            {"bg": "#ffccff", "text": "#660066"}, # Light purple
            {"bg": "#ccffff", "text": "#006666"}, # Light cyan
            {"bg": "#ffddcc", "text": "#804000"}, # Light orange
            {"bg": "#ddffcc", "text": "#336600"}  # Light lime
        ]
        
        for idx, place in enumerate(coords):
            color_idx = idx % len(marker_colors)
            place["color"] = marker_colors[color_idx]["bg"]
            place["text_color"] = marker_colors[color_idx]["text"]

        with open("coordinates.json", "w") as f:
            json.dump(coords, f)

        return render_template_string(HTML_TEMPLATE, prompt=prompt, places=coords)

    except Exception as e:
        return jsonify({
            "error": "Could not parse response from Gemini",
            "details": str(e),
            "raw_response": response.text if 'response' in locals() else "No response"
        }), 500

@app.route('/download-json')
def download_json():
    return send_file("coordinates.json", as_attachment=True)

@app.route('/map.png')
def map_png():
    show_names = request.args.get("names", "1") == "1"
    theme = request.args.get("theme", "default")

    try:
        with open("coordinates.json", "r") as f:
            places = json.load(f)
    except Exception as e:
        return jsonify({"error": "Could not load coordinates", "details": str(e)}), 500

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    marker_params = []

    # Define a list of colors for numbered markers
    marker_colors = ["red", "green", "blue", "purple", "orange", "yellow", "pink", "brown"]

    for idx, place in enumerate(places):
        lat = place["latitude"]
        lng = place["longitude"]
        color = marker_colors[idx % len(marker_colors)]
        
        # Always add numbered marker
        marker = f"markers=color:{color}%7Clabel:{idx+1}%7C{lat},{lng}"
        marker_params.append(marker)
        
        # Optionally add name labels if enabled
        if show_names:
            name = urllib.parse.quote(place["name"])
            name_marker = f"markers=size:tiny%7Clabel:%7C{lat},{lng+0.01}&markers=label:{name}%7C{lat},{lng+0.01}"
            marker_params.append(name_marker)

    markers = "&".join(marker_params)

    types = set([p.get("type", "").lower() for p in places])
    border_type = "country" if "country" in types else "province"

    # Base styles (shared across all themes)
    base_style = [
        "style=feature:water|color:0x6baed6",  # Keep water blue in all themes
        "style=element:labels|visibility:off",
        "style=feature:road|visibility:off",
        "style=feature:transit|visibility:off",
        "style=feature:poi|visibility:off",
        "style=feature:landscape|visibility:simplified",
        f"style=feature:administrative.{border_type}|visibility:on"
    ]

    # Theme-specific styles
    theme_styles = {
    "default": [],
    "dark": [
        "style=element:geometry|color:0x242f3e",
        "style=element:labels.text.fill|color:0x746855",
        "style=element:labels.text.stroke|color:0x242f3e",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ],
    "light": [
        "style=element:geometry|color:0xf5f5f5",
        "style=element:labels.text.fill|color:0x616161",
        "style=element:labels.text.stroke|color:0xf5f5f5",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "grayscale": [
        "style=feature:all|saturation:-100",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "retro": [
        "style=feature:all|element:geometry|color:0xf5deb3",
        "style=element:labels.text.fill|color:0x333300",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "night": [
        "style=element:geometry|color:0x0c0c0c",
        "style=element:labels.text.fill|color:0xffffff",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ],
    "aubergine": [
        "style=element:geometry|color:0x2e003e",
        "style=element:labels.text.fill|color:0xd2bfff",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ]
   }

    final_styles = base_style + theme_styles.get(theme, [])
    style_param = "&".join(final_styles)

    map_url = f"{base_url}?size=600x450&{markers}&{style_param}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(map_url)

    with open("map.png", "wb") as f:
        f.write(response.content)

    return send_file("map.png", mimetype="image/png")

if __name__ == '__main__':
    app.run(debug=True)