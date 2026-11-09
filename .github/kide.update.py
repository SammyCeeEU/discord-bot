import discord
import requests
from datetime import datetime, timedelta
import os

# ============================================
# ASETUKSET
# ============================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID'))
KIDE_API_URL = "https://api.kide.app/api/products"
PAGES_TO_FETCH = 4

# ============================================
# KIDE.APP HAKU
# ============================================

def fetch_kide_events():
    """Hakee tapahtumat Kide.app:sta"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://kide.app/events',
        'Origin': 'https://kide.app',
    }
    
    all_events = []
    for page in range(1, PAGES_TO_FETCH + 1):
        try:
            url = f"{KIDE_API_URL}?page={page}&pageSize=50"
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if 'model' in data:
                    all_events.extend(data['model'])
        except Exception as e:
            print(f"Virhe sivulla {page}: {e}")
    
    return all_events

def filter_events(events):
    """Suodattaa: Helsinki + seuraava 1kk + lippuja saatavilla tai ilmainen"""
    now = datetime.now()
    one_month_later = now + timedelta(days=30)
    filtered = []
    
    for event in events:
        try:
            # Parsitaan päivämäärä
            date_str = event.get('dateActualFrom', '')
            if not date_str:
                continue
            
            event_date = datetime.fromisoformat(date_str.replace('+02:00', '').replace('+00:00', ''))
            
            # Vain seuraavan 1kk tapahtumat
            if not (now <= event_date <= one_month_later):
                continue
            
            # Vain Helsinki
            place = event.get('place', '').lower()
            name = event.get('name', '').lower()
            
            is_helsinki = any(kw in place or kw in name for kw in 
                            ['helsinki', 'stoa', 'dipoli', 'tavastia', 'nosturi', 
                             'kaapelitehdas', 'jäähalli', 'messukeskus', 'hartwall'])
            
            if not is_helsinki:
                continue
            
            # Tarkistetaan lipputilanne
            has_free_tickets = event.get('hasFreeInventoryItems', False)
            has_tickets = event.get('hasInventoryItems', False)
            sales_ongoing = event.get('salesOngoing', False)
            sales_ended = event.get('salesEnded', False)
            availability = event.get('availability', 0)
            
            # Näytä vain jos: ilmainen TAI lippuja saatavilla
            is_free = has_free_tickets or (event.get('minPrice', {}).get('eur', 999) == 0)
            has_available_tickets = sales_ongoing and has_tickets and not sales_ended and availability > 0
            
            if not (is_free or has_available_tickets):
                continue
            
            # Hinta
            min_price = event.get('minPrice', {}).get('eur', 0)
            max_price = event.get('maxPrice', {}).get('eur', 0)
            
            if is_free:
                price_text = "ILMAINEN"
            elif min_price == max_price:
                price_text = f"{min_price/100:.0f}€"
            else:
                price_text = f"{min_price/100:.0f}-{max_price/100:.0f}€"
            
            filtered.append({
                'name': event.get('name', 'Nimetön'),
                'place': event.get('place', 'Tuntematon'),
                'date': event_date,
                'date_str': event_date.strftime('%d.%m.%Y %H:%M'),
                'is_free': is_free,
                'price_text': price_text,
                'url': f"https://kide.app/events/{event.get('id')}"
            })
        except Exception:
            continue
    
    filtered.sort(key=lambda x: x['date'])
    return filtered

# ============================================
# DISCORD BOT
# ============================================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Kirjauduttu: {client.user}")
    
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Kanavaa ei löytynyt!")
        await client.close()
        return
    
    # Poista botin vanhat viestit
    print("🗑️ Poistetaan vanhat viestit...")
    async for message in channel.history(limit=100):
        if message.author == client.user and message.content.startswith("📅 **Tulevia tapahtumia"):
            try:
                await message.delete()
            except:
                pass
    
    # Hae ja suodata tapahtumat
    print("🔍 Haetaan tapahtumat...")
    events = fetch_kide_events()
    filtered = filter_events(events)
    print(f"   Löydetty {len(filtered)} tapahtumaa")
    
    # Lähetä uusi viesti
    update_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    
    if filtered:
        msg = f"📅 **Tulevia tapahtumia #kideapp**\nHelsinki | Seuraava kuukausi | Päivitetty {update_time}\n\n"
        
        for event in filtered[:20]:  # Max 20 tapahtumaa
            free_tag = " 🆓" if event['is_free'] else ""
            msg += f"**{event['name']}**{free_tag}\n"
            msg += f"📍 {event['place']} | 📅 {event['date_str']}\n"
            msg += f"🎟️ {event['price_text']}\n"
            msg += f"🔗 {event['url']}\n\n"
        
        if len(filtered) > 20:
            msg += f"_...ja {len(filtered) - 20} lisää tapahtumia Kide.app:ssa_"
    else:
        msg = f"📅 **Tulevia tapahtumia #kideapp**\nHelsinki | Seuraava kuukausi | Päivitetty {update_time}\n\n"
        msg += "Ei löytynyt tapahtumia, joissa olisi lippuja saatavilla."
    
    await channel.send(msg)
    print("✅ Viesti lähetetty!")
    
    await client.close()

client.run(DISCORD_TOKEN)
