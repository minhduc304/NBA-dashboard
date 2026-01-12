import json
import time
import os

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
                            print(f"Captured Authorization token from request")
                        elif key_lower == 'user-location-token' and value and 'User-Location-Token' not in self.tokens:
                            self.tokens['User-Location-Token'] = value
                            print(f"Captured User-Location-Token from request")

            page.on('request', handle_request)

            try:
                # Navigate to login page
                print("Navigating to Underdog Fantasy login...")
                page.goto('https://underdogfantasy.com/login', wait_until='domcontentloaded')
                page.wait_for_timeout(3000)  # Give page time to fully load

                # Try multiple selectors for email/username field
                print("Filling in login credentials...")
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
                        print(f"Found email field with selector: {selector}")
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
                        print(f"Found password field with selector: {selector}")
                        break
                    except:
                        continue

                if not password_filled:
                    raise Exception("Could not find password input field")

                # Click login button
                print("Clicking login button...")
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
                        print(f"Clicked button with selector: {selector}")
                        break
                    except:
                        continue

                if not button_clicked:
                    raise Exception("Could not find login button")

                # Wait for redirect after login (give Cloudflare time to verify)
                print("Waiting for login to complete...")
                try:
                    page.wait_for_url('**/pick-em', timeout=30000)
                    print("Redirected to pick-em page")
                except:
                    # Sometimes it goes to home page first
                    print("Waiting for page to load...")
                    page.wait_for_timeout(5000)

                # Give it a moment for API requests to fire
                print("Waiting for API requests...")
                time.sleep(3)

                # Navigate to pick-em to ensure API calls are made
                if not self.tokens:
                    print("Navigating to pick-em page to trigger API calls...")
                    page.goto('https://underdogfantasy.com/pick-em', wait_until='networkidle')
                    time.sleep(2)

                if self.tokens.get('Authorization') and self.tokens.get('User-Location-Token'):
                    print("Successfully captured tokens!")
                    return self.tokens
                else:
                    raise Exception("Failed to capture tokens from network requests")

            except Exception as e:
                print(f"Error during login: {e}")
                # Create debug directory if it doesn't exist
                debug_dir = 'underdog_debug'
                os.makedirs(debug_dir, exist_ok=True)

                # Take screenshot for debugging
                screenshot_path = os.path.join(debug_dir, 'login_error.png')
                page.screenshot(path=screenshot_path)
                print(f"Screenshot saved to {screenshot_path}")

                # Save page HTML for debugging
                html_path = os.path.join(debug_dir, 'login_error.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                print(f"Page HTML saved to {html_path}")

                # Save current URL
                print(f"Current URL: {page.url}")
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

    print(f"Tokens updated in {config_path}")
    return tokens


if __name__ == "__main__":
    # Test the token refresher
    # You'll need to provide your email and password
    EMAIL = input("Enter your Underdog email: ")
    PASSWORD = input("Enter your Underdog password: ")

    tokens = refresh_tokens_in_config(EMAIL, PASSWORD)
    print("\nTokens refreshed successfully:")
    print(f"Authorization: {tokens['Authorization'][:50]}...")
    print(f"User-Location-Token: {tokens['User-Location-Token'][:50]}...")
