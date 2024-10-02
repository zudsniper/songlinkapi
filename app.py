import os
from urllib.parse import urlparse

import dotenv
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as ec
import time

from selenium.webdriver.support.wait import WebDriverWait
from selenium_stealth import stealth

# populate the environment variables
dotenv.config()

# env vars
HEADLESS = os.getenv('HEADLESS', 'True').lower() == 'true'
DEPLOYMENT = os.getenv('DEPLOYMENT', 'local')

app = Flask(__name__)

def validate_url(music_url):
    parsed_url = urlparse(music_url)
    return parsed_url.scheme in ['http', 'https'] and parsed_url.netloc

@app.route('/convert', methods=['POST'])
def convert_music_link():
    try:
        # Get the music service URL from the request
        music_url = request.json.get('url')
        if not music_url:
            return jsonify({"error": "URL not provided"}), 400
        if not validate_url(music_url):
            return jsonify({"error": "Invalid URL"}), 400

        # Use Selenium to automate the interaction with song.link
        song_link_url = get_song_link(music_url)

        if song_link_url:
            return jsonify({"song_link": song_link_url})
        else:
            return jsonify({"error": "Could not retrieve song.link URL"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_song_link(music_url):
    # Set up Selenium options
    # Set up Chrome options
    chrome_options = Options()
    if HEADLESS:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--auto-open-devtools-for-tabs")  # Opens DevTools automatically
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    if not DEPLOYMENT == 'local':
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
        chrome_service = Service(executable_path=os.environ.get("CHROMEDRIVER_PATH"))
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    # disable navigator.webdriver detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Use stealth to avoid detection
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    # Enable browser logging
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    try:
        # Navigate to the song.link homepage
        driver.get('https://odesli.co') # this redirects to a different URL so the URL wait for the next bit should work

        # Find the input element by its ID and enter the music service URL
        search_input = driver.find_element(By.ID, 'search-page-downshift-input')
        search_input.send_keys(music_url)
        search_input.send_keys(Keys.ENTER)

        print_log(driver.get_log('browser'))

        # Wait for the page to load
        WebDriverWait(driver, 5).until(ec.presence_of_element_located((By.CSS_SELECTOR, 'img[alt="Album artwork"]')))

        # Get the current URL after redirection (this will be the universal link)
        song_link_url = driver.current_url
        return song_link_url

    except TimeoutException:

        # Handle timeouts for missing elements or failed navigation

        return {"error": "The request timed out or the page took too long to load."}

    except NoSuchElementException:

        # Handle cases where expected elements are missing (like after a 400 error)

        if "400" in driver.page_source:

            return {"error": "400 Bad Request: The URL provided is invalid or the request failed."}

        else:

            return {"error": "Element not found. The page may have failed to load correctly."}

    except Exception as e:

        # Catch any other exceptions and return a general error message

        return {"error": f"An unexpected error occurred: {str(e)}"}

    finally:
        #input("Enter to close")
        driver.quit()

def print_log(logs):
    print("-"*60)
    for entry in logs:
        print(entry)


if __name__ == '__main__':
    #print(get_song_link("https://open.spotify.com/track/4JKaEsSA22eNOozaLWy4v9?si=a7f10414ec49408c"))
    app.run(debug=True)
