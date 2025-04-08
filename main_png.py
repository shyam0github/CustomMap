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
            <input type="checkbox" id="toggleLabels" checked onchange="updateMap()"> ✅ Show extracted location names
        </label>
    </div>
</div>

<!-- Main Content: Map and Table -->
<div style="display: flex; gap: 40px; padding-top: 20px; align-items: flex-start;">
    <!-- Map Section -->
    <div style="width: 60%;">
        <h3 style="margin: 0;">Generated Map</h3>
        <img id="mapImage" src="/map.png?labels=1&theme=default" alt="Map Image" style="width: 100%; border: 1px solid #ccc; margin-top: 30px;">
    </div>

    <!-- Table Section -->
    <div style="width: 40%;">
        <h3 style="margin: 0;">Historical Facts</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="width: 100%; margin-top: 30px;">
            <tr><th>Location</th><th>Historical Fact</th></tr>
            {% for p in places %}
            <tr><td>{{ p.name }}</td><td>{{ p.fact | safe | highlight_keywords }}</td></tr>
            {% endfor %}
        </table>
    </div>
</div>

<script>
    function updateMap() {
        const show = document.getElementById('toggleLabels').checked ? 1 : 0;
        const theme = document.getElementById('themeSelector').value;
        document.getElementById('mapImage').src = `/map.png?labels=${show}&theme=${theme}&t=${new Date().getTime()}`;
    }
</script>
<br>
<a href="/download-json">⬇️ Download JSON</a>
{% endif %}
'''

@app.template_filter('highlight_keywords')
def highlight_keywords(text):
    keywords = [
        r"\b\d{3,4}\b",                     # years like 1947, 1066
        r"\b(King|Queen|Empire|Dynasty|Revolution|War|Treaty|Battle|Discovery|Colonial|Independence|Invasion|Sultan|Maharaja)\b"
    ]

    for pattern in keywords:
        text = re.sub(pattern, r'<span style="color:#007bff; font-weight:bold;">\1</span>' if '\\1' in pattern else r'<span style="color:#007bff; font-weight:bold;">\g<0></span>', text, flags=re.IGNORECASE)

    return Markup(text)


@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE, prompt="", places=None)

@app.route('/get-coordinates', methods=['POST'])
def get_coordinates():
    prompt = request.form.get("prompt")

    full_prompt = f"""
You are an AI assistant. Given a user prompt that may mention one or more locations, extract each distinct place and return a JSON list.

Each item must contain:
- "name" (name of the location),
- "latitude",
- "longitude",
- "fact" (one historical fact about that location),
- "type" (either "country", "city", or "region")

Only return the raw JSON array.
Prompt: \"\"\"{prompt}\"\"\"
"""

    try:
        response = model.generate_content(full_prompt)
        cleaned = re.sub(r"```(?:json)?|```", "", response.text).strip()
        coords = json.loads(cleaned)

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
    show_labels = request.args.get("labels", "1") == "1"
    theme = request.args.get("theme", "default")

    try:
        with open("coordinates.json", "r") as f:
            places = json.load(f)
    except Exception as e:
        return jsonify({"error": "Could not load coordinates", "details": str(e)}), 500

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    marker_params = []

    for place in places:
     lat = place["latitude"]
     lng = place["longitude"]
     name = urllib.parse.quote(place["name"])
     marker = f"markers=color:red%7Clabel:%7C{lat},{lng}"
     if show_labels:
        marker += f"&markers=label:{name}%7C{lat},{lng}"
     marker_params.append(marker)

    markers = "&".join(marker_params)

    types = set([p.get("type", "").lower() for p in places])
    border_type = "country" if "country" in types else "province"

    # Base styles (shared)
    base_style = [
        "style=element:labels|visibility:off",
        "style=feature:road|visibility:off",
        "style=feature:transit|visibility:off",
        "style=feature:poi|visibility:off",
        "style=feature:landscape|visibility:simplified",
        f"style=feature:administrative.{border_type}|visibility:on",
        "style=feature:water|color:0xf0f8ff"  # Keep water blue
    ]

    # Theme-specific styles
    theme_styles = {
    "default": [],
    "dark": [
        "style=element:geometry|color:0x242f3e",
        "style=element:labels.text.fill|color:0x746855",
        "style=element:labels.text.stroke|color:0x242f3e",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ],
    "light": [
        "style=element:geometry|color:0xf5f5f5",
        "style=element:labels.text.fill|color:0x616161",
        "style=element:labels.text.stroke|color:0xf5f5f5",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "grayscale": [
        "style=feature:all|saturation:-100",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "retro": [
        "style=feature:all|element:geometry|color:0xf5deb3",
        "style=element:labels.text.fill|color:0x333300",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0x000000"
    ],
    "night": [
        "style=element:geometry|color:0x0c0c0c",
        "style=element:labels.text.fill|color:0xffffff",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ],
    "aubergine": [
        "style=element:geometry|color:0x2e003e",
        "style=element:labels.text.fill|color:0xd2bfff",
        f"style=feature:administrative.{border_type}|visibility:on",
        f"style=feature:administrative.{border_type}|element:geometry.stroke|color:0xffffff"
    ]
   }

    final_styles = base_style + theme_styles.get(theme, [])
    style_param = "&".join(final_styles)

    map_url = f"{base_url}?size=800x600&{markers}&{style_param}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(map_url)

    with open("map.png", "wb") as f:
        f.write(response.content)

    return send_file("map.png", mimetype="image/png")

if __name__ == '__main__':
    app.run(debug=True)
