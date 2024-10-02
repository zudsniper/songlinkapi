import os
from urllib.parse import urlparse

from loguru import logger
import dotenv as dotenv
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
dotenv.load_dotenv()

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
            return jsonify({"error": "Could not retrieve song.link URL after multiple attempts."}), 500
    except Exception as e:
        logger.exception("An unexpected error occurred in /convert endpoint.")
        return jsonify({"error": str(e)}), 500

def get_song_link(music_url, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Attempt {attempt} of {max_attempts} to get song.link URL.")
        driver = None  # Initialize driver within the loop
        try:
            # Set up Chrome options
            chrome_options = Options()
            if HEADLESS:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/91.0.4472.124 Safari/537.36")
            if not DEPLOYMENT == 'local':
                chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
                chrome_service = Service(executable_path=os.environ.get("CHROMEDRIVER_PATH"))
                driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)

            # Disable navigator.webdriver detection
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Use stealth to avoid detection
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True)

            # Navigate to the song.link homepage
            driver.get('https://odesli.co')

            # Find the input element by its ID and enter the music service URL
            search_input = driver.find_element(By.ID, 'search-page-downshift-input')
            search_input.send_keys(music_url)
            search_input.send_keys(Keys.ENTER)

            # Wait for the page to load
            WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.CSS_SELECTOR, 'img[alt="Album artwork"]'))
            )

            # Get the current URL after redirection (this will be the universal link)
            song_link_url = driver.current_url

            # Validate the obtained URL
            if validate_url(song_link_url):
                logger.info(f"Successfully obtained song.link URL: {song_link_url}")
                return song_link_url
            else:
                logger.warning("Invalid song_link_url obtained.")
                time.sleep(1)  # Wait before retrying
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Attempt {attempt} failed due to: {str(e)}")
            time.sleep(1)  # Wait before retrying
        except Exception as e:
            logger.exception(f"An unexpected error occurred on attempt {attempt}: {str(e)}")
            time.sleep(1)  # Wait before retrying
        finally:
            if driver:
                driver.quit()
    # If all attempts failed
    logger.error("All attempts to obtain song.link URL have failed.")
    return None

def print_log(logs):
    print("-"*60)
    for entry in logs:
        print(entry)


if __name__ == '__main__':
    app.run(debug=True)
