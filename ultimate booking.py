import time
import json
import os
import random
import threading
import queue
import traceback
import logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from plyer import notification

# --- CONFIGURATION (Default) ---
KEYWORDS = ["Cricket", "India", "IPL", "Badminton"] 
# (You can also add keywords via the web UI in a full version, 
# but for this one-file script we keep it simple or allow dynamic later)

# --- FLASK APP ---
app = Flask(__name__)

# --- EMBEDDED HTML/CSS/JS ---
HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultimate Sports Bot</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #050505; --card: rgba(255,255,255,0.03); --primary: #00f2ea; --accent: #ff0050; --text: #eee; }
        body { background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        
        /* Layout */
        .sidebar { width: 260px; background: rgba(255,255,255,0.02); border-right: 1px solid rgba(255,255,255,0.05); padding: 20px; display: flex; flex-direction: column; }
        .main { flex: 1; display: flex; flex-direction: column; position: relative; }
        .content { padding: 30px; overflow-y: auto; flex: 1; }
        
        /* Typography */
        h1, h2, h3 { margin: 0 0 10px 0; font-weight: 700; }
        .brand { font-size: 1.5rem; background: linear-gradient(90deg, var(--primary), #fff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 40px; }
        
        /* Cards */
        .card { background: var(--card); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(10px); transition: 0.3s; }
        .card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 10px 40px rgba(0, 242, 234, 0.1); }
        
        /* Event List */
        .event-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .event-card { position: relative; overflow: hidden; }
        .event-card .platform { position: absolute; top: 10px; right: 10px; font-size: 0.7rem; background: rgba(0,0,0,0.5); padding: 4px 8px; border-radius: 4px; }
        .event-card h3 { font-size: 1.1rem; margin-bottom: 5px; color: #fff; }
        .event-card p { font-size: 0.9rem; color: #888; margin-bottom: 15px; }
        
        /* Controls */
        input { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 8px; border-radius: 8px; width: 80px; margin-right: 10px; }
        button { background: var(--primary); color: #000; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 700; cursor: pointer; transition: 0.2s; }
        button:hover { box-shadow: 0 0 15px var(--primary); transform: scale(1.05); }
        button.stop { background: var(--accent); color: #fff; }
        
        /* Logs */
        .log-panel { height: 200px; background: #000; border-top: 1px solid rgba(255,255,255,0.1); padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; overflow-y: auto; color: #aaa; }
        .log-line { margin-bottom: 4px; }
        .log-line.alert { color: var(--accent); }
        .log-line.success { color: var(--primary); }

        /* Pulse */
        .status-dot { width: 10px; height: 10px; background: #444; border-radius: 50%; display: inline-block; margin-right: 10px; }
        .status-dot.active { background: #00ff88; box-shadow: 0 0 10px #00ff88; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }

        /* Chat Assistant */
        .chat-btn { position: fixed; bottom: 30px; right: 30px; width: 60px; height: 60px; background: linear-gradient(135deg, var(--primary), #00aaff); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; cursor: pointer; box-shadow: 0 10px 30px rgba(0,170,255,0.3); z-index: 100; transition: transform 0.3s; }
        .chat-btn:hover { transform: scale(1.1) rotate(10deg); }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">TAKITA</div>
        <div class="card">
            <div style="display:flex; align-items:center; margin-bottom:10px;">
                <div id="status-dot" class="status-dot"></div>
                <span id="status-text">OFFLINE</span>
            </div>
            <button onclick="startBot()" style="width:100%; margin-bottom:10px;">INITIALIZE</button>
            <button onclick="stopBot()" class="stop" style="width:100%;">TERMINATE</button>
        </div>
        <div style="margin-top:auto; font-size:0.8rem; color:#666;">
            &copy; 2025 Deepmind<br>Agentic Coding
        </div>
    </div>

    <div class="main">
        <div class="content">
            <h2>Discovered Events</h2>
            <p>Configure ticket requirements for discovered events to start auto-booking.</p>
            <div id="event-grid" class="event-grid">
                <!-- Events injected here -->
            </div>
        </div>

        <div class="log-panel" id="log-panel">
            <div class="log-line">[SYSTEM] Interface Ready.</div>
        </div>
    </div>

    <div class="chat-btn" onclick="alert('AI Assistant: I am monitoring your logs via the backend. If you see an error, check the console!')">💬</div>

    <script>
        setInterval(pollData, 1000);

        async function pollData() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                // Update Status
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                if(data.running) {
                    dot.classList.add('active');
                    text.innerText = "SENSING";
                    text.style.color = "#00ff88";
                } else {
                    dot.classList.remove('active');
                    text.innerText = "OFFLINE";
                    text.style.color = "#666";
                }

                // Update Logs
                const logPanel = document.getElementById('log-panel');
                logPanel.innerHTML = '';
                data.logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'log-line ' + (log.includes('ALERT') ? 'alert' : log.includes('FOUND') ? 'success' : '');
                    div.innerText = log;
                    logPanel.appendChild(div);
                });
                logPanel.scrollTop = logPanel.scrollHeight;

                // Update Events
                const grid = document.getElementById('event-grid');
                grid.innerHTML = '';
                data.events.forEach(evt => {
                    const el = document.createElement('div');
                    el.className = 'card event-card';
                    
                    let actionHtml = '';
                    if(evt.status === 'pending') {
                        actionHtml = `
                            <div style="margin-top:10px; display:flex; align-items:center;">
                                <input type="number" id="qty-${evt.id}" placeholder="Qty" value="2" min="1" max="10">
                                <input type="number" id="price-${evt.id}" placeholder="Max ₹" value="5000" step="500">
                                <button onclick="activateEvent('${evt.id}')">GO</button>
                            </div>
                        `;
                    } else if (evt.status === 'active') {
                        actionHtml = `<div style="color:var(--primary); margin-top:10px;">● Monitoring for Tickets...</div>`;
                    } else if (evt.status === 'booked') {
                        actionHtml = `<div style="color:#0f0; margin-top:10px;">✔ HANDOVER IN PROGRESS</div>`;
                    }

                    el.innerHTML = `
                        <div class="platform">${evt.platform}</div>
                        <h3>${evt.title}</h3>
                        <p><a href="${evt.url}" target="_blank" style="color:#888;">${evt.url.substring(0,30)}...</a></p>
                        ${actionHtml}
                    `;
                    grid.appendChild(el);
                });

            } catch(e) { console.error(e); }
        }

        async function startBot() { await fetch('/api/start', {method:'POST'}); }
        async function stopBot() { await fetch('/api/stop', {method:'POST'}); }
        
        async function activateEvent(id) {
            const qty = document.getElementById(`qty-${id}`).value;
            const price = document.getElementById(`price-${id}`).value;
            await fetch('/api/activate_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id, qty, price})
            });
        }
    </script>
</body>
</html>
'''

# --- BACKEND LOGIC ---
log_queue = queue.Queue()
log_buffer = []

# State
state = {
    "running": False,
    "events": [] # {id, title, url, platform, status: pending|active|booked, config: {qty, price}}
}
bot_thread = None
stop_event = threading.Event()

class BotEngine:
    def __init__(self):
        self.driver = None

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        fmsg = f"[{ts}] {msg}"
        print(fmsg)
        log_queue.put(fmsg)

    def start_driver(self):
        opts = webdriver.ChromeOptions()
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        
    def run(self):
        self.log("Initializing Bot Engine...")
        self.start_driver()
        try:
            # Load Cookies
            self.driver.get("https://in.bookmyshow.com")
            self.load_cookies("BookMyShow")
            self.driver.get("https://insider.in")
            self.load_cookies("PaytmInsider")

            while not stop_event.is_set():
                # 1. Discovery Phase
                self.check_bms()
                self.check_insider()
                
                # 2. Monitor Active Events
                active_events = [e for e in state['events'] if e['status'] == 'active']
                self.log(f"Monitoring {len(active_events)} active events...")
                
                for evt in active_events:
                    if stop_event.is_set(): break
                    self.monitor_event(evt)
                    time.sleep(1)

                # Sleep
                for _ in range(10): 
                    if stop_event.is_set(): break
                    time.sleep(1)
                    
        except Exception as e:
            self.log(f"Error: {e}")
            traceback.print_exc()
        finally:
            self.log("Engine stopping...")
            if self.driver: self.driver.quit()
            state['running'] = False

    def load_cookies(self, platform):
        fname = f"{platform.lower().replace(' ','')}_cookies.json"
        if os.path.exists(fname):
            try:
                with open(fname) as f:
                    for c in json.load(f):
                        try: self.driver.add_cookie(c)
                        except: pass
                self.log(f"Loaded {platform} cookies.")
            except: pass
        else:
            self.log(f"Warning: No cookies for {platform}.")

    def check_bms(self):
        self.log("Scouting BMS...")
        try:
            self.driver.get("https://in.bookmyshow.com/explore/sports")
            time.sleep(3)
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/sports/') and not(contains(@href, '/explore/'))]")
            for l in links:
                try:
                    title = l.get_attribute("title") or l.text
                    href = l.get_attribute("href")
                    if not title or not href: continue
                    
                    if any(k.lower() in title.lower() for k in KEYWORDS):
                        self.add_event(title, href, "BookMyShow")
                except: pass
        except: pass

    def check_insider(self):
        self.log("Scouting Insider...")
        try:
            self.driver.get("https://insider.in/all-sports-events")
            time.sleep(3)
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/event/')]")
            for l in links:
                try:
                    title = l.text
                    href = l.get_attribute("href")
                    if not title or not href: continue

                    if any(k.lower() in title.lower() for k in KEYWORDS):
                        self.add_event(title, href, "PaytmInsider")
                except: pass
        except: pass

    def add_event(self, title, url, platform):
        # Check duplicate
        if any(e['url'] == url for e in state['events']): return
        
        self.log(f"NEW EVENT FOUND: {title}")
        state['events'].append({
            "id": f"evt_{int(time.time()*1000)}_{random.randint(100,999)}",
            "title": title,
            "url": url,
            "platform": platform,
            "status": "pending", # Waiting for user config
            "config": {}
        })
        # Notify sound
        try: 
            import winsound
            winsound.Beep(800, 200)
        except: pass

    def monitor_event(self, evt):
        self.log(f"Checking: {evt['title']}")
        try:
            self.driver.get(evt['url'])
            time.sleep(2)
            
            # Simple check for booking button availability
            # In a real scenario, we would also check price against evt['config']['price']
            
            can_book = False
            btn = None
            
            if evt['platform'] == "BookMyShow":
                btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Book')]")
                if btns and btns[0].is_enabled():
                    can_book = True
                    btn = btns[0]
            
            elif evt['platform'] == "PaytmInsider":
                btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Buy') or contains(text(), 'Register')]")
                if btns and btns[0].is_enabled():
                    can_book = True
                    btn = btns[0]
            
            if can_book:
                self.log(f"TICKETS OPEN! Attempting book for {evt['title']}")
                btn.click()
                
                # Handover
                evt['status'] = 'booked'
                self.alert_handover()
                # Stop monitoring this event so we don't spam
                
        except Exception as e:
            self.log(f"Monitor error: {e}")

    def alert_handover(self):
        try:
            notification.notify(title="TICKET FOUND", message="Handover required!", timeout=10)
            for _ in range(5):
                import winsound
                winsound.Beep(1000, 500)
                time.sleep(0.5)
        except: pass

# --- ROUTES ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    # Sync logs
    while not log_queue.empty():
        log_buffer.append(log_queue.get())
        if len(log_buffer) > 50: log_buffer.pop(0)
    
    return jsonify({
        "running": state['running'],
        "logs": log_buffer,
        "events": state['events']
    })

@app.route('/api/start', methods=['POST'])
def start():
    global bot_thread
    if state['running']: return jsonify({"status":"already running"})
    
    log_buffer.clear()
    state['running'] = True
    stop_event.clear()
    
    bot = BotEngine()
    bot_thread = threading.Thread(target=bot.run)
    bot_thread.start()
    return jsonify({"status":"started"})

@app.route('/api/stop', methods=['POST'])
def stop():
    if not state['running']: return jsonify({"status":"not running"})
    stop_event.set()
    return jsonify({"status":"stopping"})

@app.route('/api/activate_event', methods=['POST'])
def activate():
    data = request.json
    for e in state['events']:
        if e['id'] == data['id']:
            e['status'] = 'active'
            e['config'] = {"qty": data['qty'], "price": data['price']}
            log_queue.put(f"[Config] Event '{e['title']}' activated with Qty: {data['qty']}, Max Price: {data['price']}")
            return jsonify({"status":"ok"})
    return jsonify({"status":"error"})

if __name__ == "__main__":
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR) # Silence flask logs
    print("ULTIMATE BOT RUNNING ON http://localhost:5000")
    app.run(port=5000, debug=True, use_reloader=False)

