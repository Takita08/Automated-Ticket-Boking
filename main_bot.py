import time
import pickle
import os
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from plyer import notification
import config

# Global Watchlist
watchlist = []

class BotEngine:
    def __init__(self):
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless") # Run visual for now to see what happens
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def load_cookies(self, platform_name):
        filename = f"{platform_name.lower().replace(' ', '')}_cookies.pkl"
        try:
            cookies = pickle.load(open(filename, "rb"))
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            print(f"[{platform_name}] Cookies loaded.")
            return True
        except FileNotFoundError:
            print(f"[{platform_name}] No cookie file found. Run setup_session.py first!")
            return False

    def check_bookmyshow(self):
        """Scrapes BMS Sports page for keywords"""
        print("Scouting BookMyShow...")
        try:
            self.driver.get("https://in.bookmyshow.com/explore/sports")
            time.sleep(3) # Wait for load
            
            # Find Event Cards - Generic Selector
            # Look for anchor tags that have 'sports' in their href, usually indicating a sports event detail page
            # We filter out the main nav links if any
            cards = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/sports/') and not(contains(@href, '/explore/'))]")
            
            found_count = 0
            for card in cards:
                try:
                    title = card.get_attribute("title") or card.text
                    link = card.get_attribute("href")
                    
                    if not title or not link:
                        continue

                    # Keyword Check
                    if any(keyword.lower() in title.lower() for keyword in config.KEYWORDS):
                        if link not in [x['link'] for x in watchlist]:
                            print(f"[BMS] FOUND: {title}")
                            watchlist.append({"title": title, "link": link, "platform": "BookMyShow"})
                            self.notify(f"Found Match: {title}", "New BookMyShow event detected!")
                            found_count += 1
                except:
                    continue
            print(f"BMS Scout Complete. Found {found_count} new events.")
            
        except Exception as e:
            print(f"Error checking BMS: {e}")

    def check_insider(self):
        """Scrapes Paytm Insider for keywords"""
        print("Scouting Paytm Insider...")
        try:
            # Insider sports category URL
            self.driver.get("https://insider.in/all-sports-in-mumbai") # Detecting for 'mumbai' or generic 'all-sports-lines-in-main'?? 
            # Better to use a generic search or explore page if city agnostic, but Insider is often city-specific.
            # Using 'all-sports' generic tag if possible, or fallback to main search. 
            # Let's try the generic tag page which often works: https://insider.in/all-sports-events
            self.driver.get("https://insider.in/all-sports-events")
            time.sleep(3)

            # Insider cards usually are <a> tags within a specific list
            # We look for links containing /event/
            cards = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/event/')]")

            found_count = 0
            for card in cards:
                try:
                    # Insider often mimics standard card structures
                    title = card.text # Might need refinement if text is nested
                    link = card.get_attribute("href")
                    
                    if not title or not link:
                        continue
                        
                    # Clean title - Insider cards have lots of text (date, price etc)
                    # We just check if keywords are IN the blob of text
                    if any(keyword.lower() in title.lower() for keyword in config.KEYWORDS):
                        if link not in [x['link'] for x in watchlist]:
                            print(f"[Insider] FOUND: {title[:30]}...") # Truncate log
                            watchlist.append({"title": title, "link": link, "platform": "PaytmInsider"})
                            self.notify(f"Found Match!", "New Paytm Insider event!")
                            found_count += 1
                except:
                    continue
            print(f"Insider Scout Complete. Found {found_count} new events.")

        except Exception as e:
            print(f"Error checking Insider: {e}")

    def monitor_event(self, event):
        """
        Visits a specific event URL and tries to click BOOK.
        """
        url = event['link']
        platform = event['platform']
        print(f"Monitoring ({platform}): {url}")
        
        try:
            self.driver.get(url)
            
            if platform == "BookMyShow":
                # BMS Button usually "Book" or "Buy"
                try:
                    book_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Book')]")
                    if book_btn.is_enabled():
                        self.notify("TICKETS OPEN (BMS)!", "Attempting to book...")
                        self.attempt_booking_bms(book_btn)
                    else:
                        print("BMS Book button found but disabled.")
                except:
                    print("BMS Book button not found/active.")

            elif platform == "PaytmInsider":
                # Insider Button usually "Buy Now" or "Register"
                try:
                    # Look for typical Insider CTA buttons
                    buy_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Buy Now') or contains(text(), 'Register')]")
                    if buy_btns:
                        buy_btn = buy_btns[0]
                        if buy_btn.is_enabled():
                            self.notify("TICKETS OPEN (Insider)!", "Attempting to book...")
                            self.attempt_booking_insider(buy_btn)
                        else:
                             print("Insider Buy button found but disabled.")
                    else:
                        print("Insider Buy button not found.")
                except:
                     print("Insider check failed.")

        except Exception as e:
            print(f"Error monitoring event: {e}")

    def attempt_booking_bms(self, btn_element):
        """Booking Flow for BookMyShow"""
        try:
            btn_element.click()
            time.sleep(2)
            
            # Select Quantity if popup appears
            try:
                # This is highly dependent on BMS UI which changes
                # Trying a generic "2" selection
                qty_btn = self.driver.find_element(By.ID, "pop_2") # Common ID pattern or
                if not qty_btn:
                     qty_btn = self.driver.find_element(By.XPATH, f"//li[contains(text(), '{config.TICKET_QTY}')]")
                qty_btn.click()
                
                # Proceed
                proceed_btn = self.driver.find_element(By.ID, "proceed-qty")
                proceed_btn.click()
            except:
                print("Auto-quantity selection failed/skipped (might be direct).")

            self.handover()
        except Exception as e:
            print(f"Booking attempt failed: {e}")
            self.handover()

    def attempt_booking_insider(self, btn_element):
        """Booking Flow for Paytm Insider"""
        try:
            btn_element.click()
            time.sleep(2)
            
            # Insider usually opens a modal or new page.
            # We often just need to handover immediately as seat layout scripts are complex.
            self.handover()
        except:
            self.handover()

    def handover(self):
        self.notify("ACTION REQUIRED", "Please select seats and pay!")
        print("\n" + "="*40)
        print("CRITICAL: BOT PAUSED. PLEASE SELECT SEATS & PAY.")
        print("="*40 + "\n")
        # Loop forever beep
        while True:
            import winsound
            try:
                winsound.Beep(1000, 500)
            except:
                pass
            time.sleep(1)

    def notify(self, title, message):
        print(f"ALERT: {title} - {message}")
        if config.ENABLE_SOUND:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=10
                )
            except:
                pass
    
    def run(self):
        print("Bot Engine Started...")
        # 1. Load Sessions
        self.driver.get("https://in.bookmyshow.com")
        self.load_cookies("BookMyShow")
        
        # Insider often redirects to home, so just load cookies on home
        self.driver.get("https://insider.in")
        self.load_cookies("PaytmInsider")
        
        # 2. Loop
        while True:
            print("\n--- Starting Scout Cycle ---")
            # Phase A: Discovery
            self.check_bookmyshow()
            self.check_insider()
            
            # Phase B: Monitor Watchlist
            print(f"Monitoring {len(watchlist)} events in watchlist...")
            for item in watchlist:
                self.monitor_event(item)
                time.sleep(2) 
            
            print("Cycle check complete. Sleeping 30s...")
            time.sleep(30)

if __name__ == "__main__":
    bot = BotEngine()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Bot Stopped.")
        bot.driver.quit()
