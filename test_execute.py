from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Capture console logs
    page.on("console", lambda msg: print(f"Browser console: {msg.type}: {msg.text}"))
    page.on("pageerror", lambda err: print(f"Browser error: {err}"))
    
    # Capture network responses
    def handle_response(response):
        if 'api/v1/trading/place-order' in response.url or 'execute' in response.url:
            print(f"Network response {response.url}: {response.status}")
            try:
                print(f"Response body: {response.json()}")
            except:
                pass
                
    page.on("response", handle_response)
    
    print("Navigating to Grok page...")
    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')
    
    print("Clicking Grok Tab...")
    try:
        page.locator('text=GROK').click()
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Failed to click GROK: {e}")
        
    print("Clicking EXECUTE button...")
    try:
        page.locator('button:has-text("EXECUTE")').first.click()
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Failed to click EXECUTE: {e}")
    
    browser.close()
