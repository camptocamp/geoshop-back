import os
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions

SELENIUM_LOCAL = os.environ.get('SELENIUM_LOCAL', 'False') == 'True'
SELENIUM_HOST = os.environ.get('SELENIUM_HOST', "http://selenium:4444") + "/wd/hub"
FRONTEND_HOST = os.environ.get('FRONTEND_HOST', "http://frontend")

REQUEST_PROCESS_WAIT = 20  # Seconds (Selenium default time unit)
EXTRACT_DEMO_LOGIN = ("admin", "motdepasse21")
GEOSHOP_DEMO_LOGIN = ("admin", "Test1234")

class ExtractStatusTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        options = webdriver.FirefoxOptions()
        options.add_argument("--web-security=no")
        options.add_argument("--ssl-protocol=any")
        options.add_argument("--ignore-ssl-errors=yes")
        if SELENIUM_LOCAL:
            cls._driver = webdriver.Firefox(options=options)
        else:
            cls._driver = webdriver.Remote(command_executor=SELENIUM_HOST, options=options)

    @classmethod
    def tearDownClass(cls):
        cls._driver.close()

    def test_geoshopLoginLogout(self):
        self._driver.get(f"{FRONTEND_HOST}/geoshop")
        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title").get_attribute("innerText"),
            "Geoshop API"
        ) 
        
        # Login
        self._driver.find_element(By.LINK_TEXT, "Admin").click()
        self._driver.find_element(By.ID, "id_username").send_keys(GEOSHOP_DEMO_LOGIN[0])
        self._driver.find_element(By.ID, "id_password").send_keys(GEOSHOP_DEMO_LOGIN[1])
        self._driver.find_element(By.CSS_SELECTOR, "input[value='Log in']").click()

        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title").get_attribute("innerText"),
            "Site administration | GeoShop Admin",
        )

        # Logout
        self._driver.find_element(By.CSS_SELECTOR, "#logout-form button").click()
        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title").get_attribute("innerText"),
            "Logged out | GeoShop Admin"
        )


    def test_extractLoginLogout(self):
        self._driver.get(f"{FRONTEND_HOST}/extract")
        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title").get_attribute("innerText"),
            "Extract",
        )

        # Login
        self._driver.find_element(By.NAME, "username").send_keys(EXTRACT_DEMO_LOGIN[0])
        self._driver.find_element(By.NAME, "password").send_keys(EXTRACT_DEMO_LOGIN[1])
        self._driver.find_element(By.ID, "loginButton").click()
        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title")
            .get_attribute("innerText")
            .strip(),
            "Extract – Accueil",
        )

        self._driver.find_element(By.ID, "logoutLink").click()
        self.assertEqual(
            self._driver.find_element(By.TAG_NAME, "title")
            .get_attribute("innerText")
            .strip(),
            "Extract",
        )


if __name__ == "__main__":
    unittest.main()
