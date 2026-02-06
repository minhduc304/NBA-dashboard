import json
import logging
import time
import os

import requests

try:
    from playwright.sync_api import sync_playwright
    playwright_available = True
except ImportError:
    playwright_available = False
    sync_playwright = None

try:
    from playwright_stealth import Stealth
    stealth_available = True
except ImportError:
    stealth_available = False

logger = logging.getLogger(__name__)

# Auth0 config extracted from Underdog's JWT claims
AUTH0_TOKEN_URL = "https://login.underdogsports.com/oauth/token"
AUTH0_CLIENT_ID = "cQvYz1T2BAFbix4dYR37dyD9O0Thf1s6"
AUTH0_AUDIENCE = "https://api.underdogfantasy.com"


def refresh_auth_token(email, password):
    """
    Refresh the Authorization token via Auth0 password grant.
    Returns the new access token string, or raises on failure.
    """
    response = requests.post(AUTH0_TOKEN_URL, json={
        "grant_type": "password",
        "client_id": AUTH0_CLIENT_ID,
        "username": email,
        "password": password,
        "audience": AUTH0_AUDIENCE,
        "scope": "offline_access",
    }, timeout=15)

    if response.status_code != 200:
        raise Exception(
            f"Auth0 token refresh failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise Exception("Auth0 response missing access_token")

    logger.info("Auth token refreshed via Auth0 password grant")
    return access_token


class TokenRefresher:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.tokens = {}

    def get_tokens(self):
        """
        Automate login to Underdog Fantasy and extract authentication tokens
        """
        if not playwright_available:
            raise ImportError(
                "Playwright is required for auto token refresh. "
                "Install with: pip install playwright && playwright install chromium"
            )
        with sync_playwright() as p:
            # Launch browser (set headless=False to see what's happening)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            # Apply stealth to avoid bot detection
            if stealth_available:
                stealth = Stealth()
                stealth.apply_stealth_sync(page)

            # Intercept network requests to capture tokens
            def handle_request(request):
                if 'api.underdogfantasy.com' in request.url:
                    headers = request.headers
                    # Try both lowercase and capitalized header names
                    for key, value in headers.items():
                        key_lower = key.lower()
                        # Only capture non-empty tokens, and only once per token type
                        if key_lower == 'authorization' and value and 'Authorization' not in self.tokens:
                            self.tokens['Authorization'] = value
                        elif key_lower == 'user-location-token' and value and 'User-Location-Token' not in self.tokens:
                            self.tokens['User-Location-Token'] = value

            page.on('request', handle_request)

            try:
                # Navigate to login page
                page.goto('https://underdogfantasy.com/login', wait_until='domcontentloaded')
                page.wait_for_timeout(3000)  # Give page time to fully load

                # Try multiple selectors for email/username field
                email_selectors = [
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[name="username"]',
                    'input[placeholder*="email" i]',
                    'input[id*="email"]',
                ]

                email_filled = False
                for selector in email_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        page.fill(selector, self.email)
                        email_filled = True
                        break
                    except:
                        continue

                if not email_filled:
                    raise Exception("Could not find email input field")

                # Try multiple selectors for password field
                password_selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                ]

                password_filled = False
                for selector in password_selectors:
                    try:
                        page.fill(selector, self.password)
                        password_filled = True
                        break
                    except:
                        continue

                if not password_filled:
                    raise Exception("Could not find password input field")

                # Click login button
                button_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Log in")',
                    'button:has-text("Sign in")',
                    'button:has-text("Login")',
                ]

                button_clicked = False
                for selector in button_selectors:
                    try:
                        page.click(selector, timeout=5000)
                        button_clicked = True
                        break
                    except:
                        continue

                if not button_clicked:
                    raise Exception("Could not find login button")

                # Wait for redirect after login (give Cloudflare time to verify)
                try:
                    page.wait_for_url('**/pick-em', timeout=30000)
                except:
                    # Sometimes it goes to home page first
                    page.wait_for_timeout(5000)

                # Give it a moment for API requests to fire
                time.sleep(3)

                # Navigate to pick-em to ensure API calls are made
                if not self.tokens:
                    page.goto('https://underdogfantasy.com/pick-em', wait_until='networkidle')
                    time.sleep(2)

                if self.tokens.get('Authorization') and self.tokens.get('User-Location-Token'):
                    return self.tokens
                else:
                    raise Exception("Failed to capture tokens from network requests")

            except Exception as e:
                # Create debug directory if it doesn't exist
                debug_dir = 'underdog_debug'
                os.makedirs(debug_dir, exist_ok=True)

                # Take screenshot for debugging
                screenshot_path = os.path.join(debug_dir, 'login_error.png')
                page.screenshot(path=screenshot_path)

                # Save page HTML for debugging
                html_path = os.path.join(debug_dir, 'login_error.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())

                raise
            finally:
                browser.close()


def refresh_tokens_in_config(email, password, config_path=None):
    """
    Refresh tokens and update the config file
    """
    refresher = TokenRefresher(email, password)
    tokens = refresher.get_tokens()

    # Default config path relative to this file
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'underdog_config.json')

    # Read existing config
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Update tokens
    config['headers']['Authorization'] = tokens['Authorization']
    config['headers']['User-Location-Token'] = tokens['User-Location-Token']

    # Write back to config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

    return tokens


if __name__ == "__main__":
    # Test the token refresher
    # You'll need to provide your email and password
    EMAIL = input("Enter your Underdog email: ")
    PASSWORD = input("Enter your Underdog password: ")

    tokens = refresh_tokens_in_config(EMAIL, PASSWORD)
