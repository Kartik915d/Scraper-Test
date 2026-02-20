import os
import re
import requests
import textwrap
import getpass
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==========================================
# CONFIG
# ==========================================

URL = "https://elpais.com/opinion/"
IMAGE_FOLDER = "article_images"


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def download_image(image_url, file_path):
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            f.write(response.content)

    except Exception as e:
        print("Image download failed:", e)


# ==========================================
# MAIN SCRAPER FUNCTION
# ==========================================

def scrape_articles(driver, session_name="Local"):
    print("\n==============================")
    print("Running Session:", session_name)
    print("==============================")

    try:
        driver.get(URL)

        # Accept cookies (if visible)
        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
            )
            cookie_btn.click()
            print("Cookies accepted.")
        except TimeoutException:
            pass

        # Get first 5 article links
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article header h2 a"))
        )

        articles = driver.find_elements(By.CSS_SELECTOR, "article header h2 a")[:5]
        links = [a.get_attribute("href") for a in articles]

        if not links:
            print("No articles found.")
            return

        os.makedirs(IMAGE_FOLDER, exist_ok=True)

        titles_spanish = []

        # Visit each article
        for i, link in enumerate(links, 1):
            print("\nArticle", i)
            driver.get(link)

            # Get title
            try:
                title = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                ).text

                print("Title (ES):", title)
                titles_spanish.append(title)

            except TimeoutException:
                print("Title not found.")
                titles_spanish.append("Unknown")

            # Get first paragraph
            try:
                paragraph = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "p.a_st"))
                ).text

                wrapped = textwrap.fill(paragraph, width=80)
                print("Content:\n", wrapped)

            except TimeoutException:
                print("Paragraph not found.")

            # Get image
            try:
                image = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article img, figure img"))
                )

                image_url = image.get_attribute("src")

                if image_url:
                    file_name = f"{session_name}_{i}.jpg"
                    file_path = os.path.join(IMAGE_FOLDER, file_name)
                    download_image(image_url, file_path)
                    print("Image saved:", file_path)

            except TimeoutException:
                print("Image not found.")

        # ==========================================
        # TRANSLATE TITLES
        # ==========================================

        print("\nTranslated Titles:")

        try:
            translator = GoogleTranslator(source="es", target="en")
            titles_english = translator.translate_batch(titles_spanish)

            for idx, t in enumerate(titles_english, 1):
                print(idx, "-", t)

        except Exception as e:
            print("Translation failed:", e)
            titles_english = []

        # ==========================================
        # WORD FREQUENCY
        # ==========================================

        print("\nWord Frequency (Repeated more than 2 times):")

        words = []

        for title in titles_english:
            clean_words = re.findall(r"\b\w+\b", title.lower())
            words.extend(clean_words)

        count = Counter(words)

        repeated = False
        for word, freq in count.items():
            if freq > 2:
                print(word, "->", freq)
                repeated = True

        if not repeated:
            print("No word repeated more than twice.")

        print("\nSession Finished:", session_name)

    except Exception as e:
        print("Error occurred:", e)

    finally:
        driver.quit()


# ==========================================
# BROWSERSTACK SETTINGS
# ==========================================

def get_environments():
    return [
        {"browserName": "Chrome",
         "bstack:options": {"os": "Windows", "osVersion": "11", "sessionName": "Windows Chrome"}},

        {"browserName": "Firefox",
         "bstack:options": {"os": "OS X", "osVersion": "Ventura", "sessionName": "Mac Firefox"}},

        {"browserName": "Edge",
         "bstack:options": {"os": "Windows", "osVersion": "10", "sessionName": "Windows Edge"}}
    ]


def run_browserstack_test(caps, hub_url):
    options = webdriver.ChromeOptions()

    for key, value in caps.items():
        options.set_capability(key, value)

    driver = webdriver.Remote(
        command_executor=hub_url,
        options=options
    )

    scrape_articles(driver, caps["bstack:options"]["sessionName"])


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print("\nEnter BrowserStack credentials (or press Enter to skip cloud test)\n")

    username = input("Username: ").strip()

    if username:
        access_key = getpass.getpass("Access Key: ").strip()
        hub_url = f"https://{username}:{access_key}@hub-cloud.browserstack.com/wd/hub"
    else:
        hub_url = None

    # Run locally
    print("\nStarting Local Test...\n")
    local_driver = webdriver.Chrome()
    scrape_articles(local_driver, "Local")

    # Run on BrowserStack
    if hub_url:
        print("\nStarting BrowserStack Tests...\n")

        environments = get_environments()

        with ThreadPoolExecutor(max_workers=3) as executor:
            for env in environments:
                executor.submit(run_browserstack_test, env, hub_url)

    else:
        print("\nBrowserStack test skipped.")