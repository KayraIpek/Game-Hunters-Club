from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor # Hızlandırma motorumuz
# Aynı anda veri çekimi yapabilmek için
from datetime import datetime # Tarih/Saat için (Güncellik)

app = Flask(__name__)

# Tarayıcı gibi görünmek için gerekli kimlik bilgisi (Fake ID)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def get_steam_data():
    """Steam İndirimli Oyunları - Paralel çalışacak"""
    base_url = "https://store.steampowered.com/search/results/"
    games_list = []
    # print("--- Steam Taranıyor... ---")
    
    max_pages = 3 
    count_per_page = 50 
    
    start = 0
    page = 1
    # En baştan başlayarak sayfaları taramak için

    while page <= max_pages:  # Türkçe içeriklerden oluşan verileri her seferinde 50 tane olacak şekilde 3 sayfa boyunca çek.
        params = {
            'specials': 1,
            'l': 'turkish',
            'start': start,
            'count': count_per_page,
            'infinite': 1
        }
        
        try:
            response = requests.get(base_url, headers=HEADERS, params=params, timeout=10)  # "Timeout" duruma göre değiştir
            if response.status_code == 200:
                data = response.json()
                html_content = data.get('results_html', '')
                
                soup = BeautifulSoup(html_content, 'html.parser')
                rows = soup.select('a.search_result_row') # Oyunları kaydet
                
                if not rows: break

                for row in rows:
                    try:   # Temizlik...
                        title = row.find('span', class_='title').text.strip()  
                        price_div = row.find('div', class_='discount_final_price')
                        price = price_div.text.strip() if price_div else "Fiyat Yok"
                        
                        # --- LİNK DÜZELTME (Fix) ---
                        raw_link = row.get('href', '')  # hypertext reference
                        link = raw_link.split('?')[0] if raw_link else ""

                        # Makyaj
                        img_tag = row.find('img')
                        img_url = img_tag.get('src') if img_tag else ""
                        
                        games_list.append({
                            'name': title, 'price': price, 'image': img_url, 'link': link, 'store': 'steam'
                        })
                    except: continue  # Oyun atla
                
                start += count_per_page
                page += 1
                time.sleep(0.5) 
            else:
                break
        except Exception as e:
            print(f"Steam Hatası: {e}")
            break
            
    return games_list

def get_itchio_data():
    """Itch.io - Paralel çalışacak"""
    base_url = "https://itch.io/games/on-sale"
    games_list = []
    # print("--- Itch.io Taranıyor... ---")

    max_pages = 3
    current_page = 1

    session = requests.Session()
    session.headers.update(HEADERS)
    # İstemcinin sunucuya giriş yapıp sunucudan çıkış yaptığı aralık.

    while current_page <= max_pages:
        try:
            url = f"{base_url}?page={current_page}"
            response = session.get(url, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                cells = soup.find_all('div', class_='game_cell')
                # Oyun kartı oluştur. Kart boşsa kodu kır.

                if not cells: break
                
                for cell in cells:
                    try:
                        title_tag = cell.find('a', class_='title')
                        if not title_tag: continue
                        title = title_tag.text.strip()
                        
                        link = title_tag.get('href')
                        if link and not link.startswith('http'):
                            link = f"https://itch.io{link}"

                        price_tag = cell.find('div', class_='price_value') or cell.find('div', class_='sale_tag')
                        price = price_tag.text.strip() if price_tag else "İndirimde"
                        
                        img_div = cell.find('div', class_='game_thumb')
                        img_url = img_div.get('data-background_image', '') if img_div else ""
                        
                        games_list.append({
                            'name': title, 'price': price, 'image': img_url, 'link': link, 'store': 'itch'
                        })
                    except: continue
                
                current_page += 1
                time.sleep(1)
            else:
                break

        except Exception as e:
            # print(f"Itch Hata (Sayfa {current_page}): {e}")
            current_page += 1
            continue
            
    return games_list

def get_epic_data():
    """Epic Games - Paralel çalışacak"""
    games_list = []
    # print("--- Epic Games Taranıyor... ---")
    
    # 1. Kısım: Ücretsizler
    try:
        free_url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        response = requests.get(free_url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            elements = data['data']['Catalog']['searchStore']['elements']

            for game in elements:
                promotions = game.get('promotions')
                if promotions and promotions.get('promotionalOffers') and len(promotions['promotionalOffers']) > 0:
                    title = game['title']
                    slug = game.get('productSlug') or game.get('urlSlug')
                    
                    if not slug:
                         for attr in game.get('customAttributes', []):
                            if attr.get('key') == 'com.epicgames.app.productSlug':
                                slug = attr.get('value')
                                break
                    
                    link = f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/tr/"
                    
                    img_url = ""
                    for img in game.get('keyImages', []):
                        if img.get('type') in ['Thumbnail', 'OfferImageWide', 'DieselStoreFrontWide']:
                            img_url = img.get('url')
                            break
                    
                    games_list.append({
                        'name': title, 'price': "ÜCRETSİZ", 'image': img_url, 'link': link, 'store': 'epic'
                    })
    except Exception:
        pass

    # 2. Kısım: CheapShark (Epic İndirimleri)
    try:
        cs_url = "https://www.cheapshark.com/api/1.0/deals?storeID=25&pageSize=20&sortBy=Savings"
        response = requests.get(cs_url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            deals = response.json()
            for deal in deals:
                title = deal.get('title')
                if any(g['name'] == title for g in games_list): continue
                
                normal_price = deal.get('normalPrice')
                sale_price = deal.get('salePrice')
                thumb = deal.get('thumb')
                deal_id = deal.get('dealID')
                link = f"https://www.cheapshark.com/redirect?dealID={deal_id}"
                
                games_list.append({
                    'name': title, 'price': f"${normal_price} -> ${sale_price}", 'image': thumb, 'link': link, 'store': 'epic'
                })
    except Exception:
        pass

    return games_list

@app.route('/')
def index():
    print("\n--- Game Hunter Taraması Başlıyor... ---")
    start_time = time.time()
    
    # --- PARALEL TARAMA ---
    with ThreadPoolExecutor() as executor:
        future_steam = executor.submit(get_steam_data)
        future_itch = executor.submit(get_itchio_data)
        future_epic = executor.submit(get_epic_data)
        
        steam = future_steam.result()
        itch = future_itch.result()
        epic = future_epic.result()
    
    print(f"Tarama Bitti! Süre: {time.time() - start_time:.2f} saniye")
    
    # Şu anki zamanı formatla (Örn: 25.12.2025 - 14:30)
    simdi = datetime.now().strftime("%d.%m.%Y - %H:%M")
    
    return render_template('index.html', steam_games=steam, itch_games=itch, epic_games=epic, current_time=simdi)

if __name__ == '__main__':

    app.run(debug=True, port=5001)
