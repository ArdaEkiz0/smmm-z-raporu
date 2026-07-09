import os, sys, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

APP_URL = os.environ.get("APP_URL", "https://smmm-z-raporu.streamlit.app")

def main():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(APP_URL)
        try:
            btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'get this app back up')]")
                )
            )
            btn.click()
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-testid='stAppViewContainer']")
                )
            )
        except TimeoutException:
            pass
        time.sleep(3)
        print(f"OK: {APP_URL}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        driver.quit()

if __name__ == "__main__":
    sys.exit(main())
