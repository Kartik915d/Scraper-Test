import os
import re
import requests
import textwrap
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ==========================================
# CONFIGURATION
# ==========================================
OPINION_URL = "https://elpais.com/opinion/"
IMAGES_DIR = "article_images"

# Fetch credentials from environment variables for security
BROWSERSTACK_USERNAME = os.environ.get("BROWSERSTACK_USERNAME", "YOUR_USERNAME")
BROWSERSTACK_ACCESS_KEY = os.environ.get("BROWSERSTACK_ACCESS_KEY", "YOUR_ACCESS_KEY")
BS_HUB_URL = f"https://{"kartikdubey_G5n4I0"}:{"rUqEYqZufnLyyjsLJUtJ"}@hub-cloud.browserstack.com/wd/hub"

def download_image(url, filepath):
    """Safely downloads an image without crashing the scraper on failure."""
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
    except Exception as e:
        print(f"      [!] Image download failed: {e}")

def scrape_and_analyze(driver, session_name="Local"):
    """Core logic: Scrapes El País, translates titles, and analyzes word frequency."""
    try:
        print(f"\n{'='*60}\n[{session_name}] STARTING EXECUTION\n{'='*60}")
        driver.get(OPINION_URL)

        # 1. Handle Cookie Consent to prevent elements from being blocked
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
            )
            cookie_btn.click()
            print(f"[{session_name}] Accepted cookies.")
        except TimeoutException:
            pass  # No cookie popup appeared

        # 2. Extract URLs First to avoid StaleElementReferenceException
        print(f"[{session_name}] Locating articles...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article header h2 a"))
        )
        article_links = driver.find_elements(By.CSS_SELECTOR, "article header h2 a")[:5]
        urls = [link.get_attribute("href") for link in article_links]

        if not urls:
            raise ValueError("Could not find any article URLs. CSS selectors may have changed.")

        os.makedirs(IMAGES_DIR, exist_ok=True)
        spanish_titles = []

        # 3. Scrape Each Article
        for idx, url in enumerate(urls, 1):
            print(f"\n--- [{session_name}] Article {idx} ---")
            driver.get(url)
            
            # Extract Heading (h1)
            try:
                title_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                title = title_el.text
                spanish_titles.append(title)
                print(f"Heading (ES): {title}")
            except TimeoutException:
                print("Heading: [!] Not found")
                spanish_titles.append("Unknown")

            # Extract Content (Using the specific `p.a_st` class you identified)
            try:
                content_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "p.a_st"))
                )
                content = content_el.text
                # Wrap text so it formats beautifully in the terminal
                wrapped_content = textwrap.fill(content, width=80, initial_indent="  ", subsequent_indent="  ")
                print("Content (ES):")
                print(wrapped_content)
            except TimeoutException:
                print("Content (ES): [!] Paragraph with class 'p.a_st' not found.")

            # Extract Image
            try:
                img_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article img, figure img"))
                )
                img_url = img_el.get_attribute("src")
                if img_url:
                    img_path = os.path.join(IMAGES_DIR, f"cover_{session_name.replace(' ', '_')}_{idx}.jpg")
                    download_image(img_url, img_path)
                    print(f"Cover Image : Saved to {img_path}")
            except TimeoutException:
                print("Cover Image : [!] No image found.")

        # 4. Translate Titles
        print(f"\n--- [{session_name}] Translated Headers ---")
        try:
            translator = GoogleTranslator(source='es', target='en')
            translated_titles = translator.translate_batch(spanish_titles)
            for i, t in enumerate(translated_titles, 1):
                print(f"{i}. {t}")
        except Exception as e:
            print(f"Translation failed: {e}")
            translated_titles = []

        # 5. Analyze Repeated Words
        print(f"\n--- [{session_name}] Word Frequency Analysis ---")
        all_words = []
        for title in translated_titles:
            # Extract only alphanumeric words, converted to lowercase
            words = re.findall(r'\b\w+\b', title.lower())
            all_words.extend(words)

        word_counts = Counter(all_words)
        repeated = {w: c for w, c in word_counts.items() if c > 2}
        
        if repeated:
            print("Words repeated more than twice across all translated headers:")
            for word, count in repeated.items():
                print(f"  - '{word}': {count} times")
        else:
            print("  No words were repeated more than twice.")

        print(f"\n{'='*60}\n[{session_name}] EXECUTION COMPLETE\n{'='*60}")

        # Mark test as Passed on BrowserStack dashboard
        if session_name != "Local":
            driver.execute_script('browserstack_executor: {"action": "setSessionStatus", "arguments": {"status":"passed", "reason": "Successfully scraped and analyzed!"}}')

    except Exception as e:
        print(f"[{session_name}] Critical Error: {e}")
        # Mark test as Failed on BrowserStack dashboard
        if session_name != "Local":
             driver.execute_script(f'browserstack_executor: {{"action": "setSessionStatus", "arguments": {{"status":"failed", "reason": "Script threw an exception."}} }}')
    finally:
        driver.quit()

# ==========================================
# BROWSERSTACK ENVIRONMENTS
# ==========================================
def get_browserstack_environments():
    return [
        {"bstack:options": {"os": "Windows", "osVersion": "11", "sessionName": "Windows Chrome"}, "browserName": "Chrome"},
        {"bstack:options": {"os": "OS X", "osVersion": "Ventura", "sessionName": "Mac Firefox"}, "browserName": "Firefox"},
        {"bstack:options": {"os": "Windows", "osVersion": "10", "sessionName": "Windows Edge"}, "browserName": "Edge"},
        {"bstack:options": {"deviceName": "Samsung Galaxy S22", "osVersion": "12.0", "sessionName": "Android Chrome"}, "browserName": "chrome"},
        {"bstack:options": {"deviceName": "iPhone 14", "osVersion": "16", "sessionName": "iOS Safari"}, "browserName": "safari"}
    ]

def run_remote_test(env_caps):
    """Initializes remote WebDriver and runs the scraping logic."""
    session_name = env_caps["bstack:options"]["sessionName"]
    options = webdriver.ChromeOptions() 
    for key, value in env_caps.items():
        options.set_capability(key, value)
    
    driver = webdriver.Remote(command_executor=BS_HUB_URL, options=options)
    scrape_and_analyze(driver, session_name)

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # 1. LOCAL EXECUTION
    print("Initializing Local WebDriver...")
    local_options = webdriver.ChromeOptions()
    local_driver = webdriver.Chrome(options=local_options)
    scrape_and_analyze(local_driver, "Local")

    # 2. BROWSERSTACK CLOUD EXECUTION (5 Parallel Threads)
    print("\nInitializing BrowserStack Parallel Execution...")
    envs = get_browserstack_environments()
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(run_remote_test, envs)