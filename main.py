import os
import json
import requests
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase'i environment variable'dan başlat
firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
if firebase_creds:
    cred_dict = json.loads(firebase_creds)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
else:
    print('FIREBASE_CREDENTIALS bulunamadi!')
    exit(1)
    firebase_admin.initialize_app(cred)

db = firestore.client()

API_KEY = os.environ.get('FOOTBALL_API_KEY')
BASE_URL = 'https://v3.football.api-sports.io'

LEAGUE_IDS = {
    'Süper Lig': 203,
    'Premier League': 39,
    'La Liga': 140,
    'Serie A': 135,
    'Bundesliga': 78,
    'Ligue 1': 61,
    'Champions League': 2,
    'Europa League': 3,
    'MLS': 253,
    'Eredivisie': 88,
}

def get_season():
    now = datetime.now()
    return str(now.year) if now.month >= 8 else str(now.year - 1)

def fetch_matches():
    now = datetime.utcnow()
    week_later = now + timedelta(days=7)
    from_date = now.strftime('%Y-%m-%d')
    to_date = week_later.strftime('%Y-%m-%d')
    season = get_season()

    headers = {'x-apisports-key': API_KEY}
    all_matches = []

    for league_name, league_id in LEAGUE_IDS.items():
        try:
            url = f'{BASE_URL}/fixtures'
            params = {
                'league': league_id,
                'from': from_date,
                'to': to_date,
                'season': season,
                'timezone': 'UTC'
            }
            response = requests.get(url, headers=headers, params=params, timeout=15)
            data = response.json()

            if response.status_code == 200 and not data.get('errors'):
                fixtures = data.get('response', [])
                for f in fixtures:
                    match = {
                        'id': str(f['fixture']['id']),
                        'league': league_name,
                        'leagueLogo': f['league'].get('logo', ''),
                        'homeTeam': f['teams']['home']['name'],
                        'awayTeam': f['teams']['away']['name'],
                        'homeTeamShort': f['teams']['home']['name'][:3].upper(),
                        'awayTeamShort': f['teams']['away']['name'][:3].upper(),
                        'homeTeamLogo': f['teams']['home'].get('logo', ''),
                        'awayTeamLogo': f['teams']['away'].get('logo', ''),
                        'matchTime': f['fixture']['date'],
                        'isLive': f['fixture']['status']['short'] in ['1H', '2H', 'HT', 'LIVE'],
                        'score': f'{f["goals"]["home"]}-{f["goals"]["away"]}' if f['goals']['home'] is not None else None,
                        'updatedAt': datetime.utcnow().isoformat(),
                    }
                    all_matches.append(match)
                print(f'{league_name}: {len(fixtures)} mac bulundu')
            else:
                print(f'{league_name} hata: {data.get("errors")}')
        except Exception as e:
            print(f'{league_name} hatasi: {e}')

    return all_matches

def save_to_firestore(matches):
    # Önce eski maçları sil
    old_matches = db.collection('matches').stream()
    batch = db.batch()
    count = 0
    for doc in old_matches:
        batch.delete(doc.reference)
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()

    # Yeni maçları ekle
    batch = db.batch()
    count = 0
    for match in matches:
        ref = db.collection('matches').document(match['id'])
        batch.set(ref, match)
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    print(f'Toplam {count} mac Firestore\'a kaydedildi')

if __name__ == '__main__':
    print('Maclar cekiliyor...')
    matches = fetch_matches()
    print(f'Toplam {len(matches)} mac bulundu')
    save_to_firestore(matches)
    print('Tamamlandi!')
