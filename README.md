# CustomMap

#### It makes custom google map png of given prompt. 

![Browser view](images\Browser_view.png)

# KEYS:

Retrieve Google map Static API key
[Visit Google map API](https://developers.google.com/maps/documentation/maps-static/get-api-key)

Retrieve Gemini API key
[Visit Google AI Studio](https://aistudio.google.com/app/apikey)

# Setup Environment variables 

Create .env file and Add
GEMINI_API_KEY="Your API Key"
MAPS_API_KEY="Your API Key"

Put this file into .gitignore 

# Install Python and the Python extension for VSCode

[Install Python](https://code.visualstudio.com/docs/languages/python#_install-python-and-the-python-extension)

# Set virtual Environment
[Create Environment](https://code.visualstudio.com/docs/python/environments#_using-the-create-environment-command)

# Import Libraries

from flask import Flask, request, jsonify, send_file, render_template_string
 Instal>> pip install flask

import google.generativeai as genai
 Install the package>> pip install google-generativeai

import json
import re
import urllib.parse
import os

import requests
Install>> pip install requests

from dotenv import load_dotenv
 Install>> pip install python-dotenv

from markupsafe import Markup
 Install>> pip install markupsafe

