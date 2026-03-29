from operator import index

import requests
import json
import pandas as pd
from datetime import datetime,timedelta,date
from dotenv import load_dotenv
import os
import streamlit as st
from urllib.parse import urlencode
from io import StringIO

load_dotenv(override=True)

nifty_dict = {
    "M&M": 519937,
    "ETERNAL": 1304833,
    "EICHERMOT": 232961,
    "SHRIRAMFIN": 1102337,
    "INDIGO": 2865921,
    "ADANIENT": 6401,
    "BAJFINANCE": 81153,
    "TMPV": 884737,
    "LT": 2939649,
    "TRENT": 502785,
    "BAJAJ-AUTO": 4267265,
    "HINDALCO": 348929,
    "TITAN": 897537,
    "SBIN": 779521,
    "TATASTEEL": 895745,
    "ADANIPORTS": 3861249,
    "JIOFIN": 4644609,
    "BAJAJFINSV": 4268801,
    "SUNPHARMA": 857857,
    "DRREDDY": 225537,
    "MARUTI": 2815745,
    "BHARTIARTL": 2714625,
    "APOLLOHOSP": 40193,
    "ICICIBANK": 1270529,
    "HINDUNILVR": 356865,
    "AXISBANK": 1510401,
    "RELIANCE": 738561,
    "KOTAKBANK": 492033,
    "JSWSTEEL": 3001089,
    "SBILIFE": 5582849,
    "ITC": 424961,
    "GRASIM": 315393,
    "MAXHEALTH": 5728513,
    "BEL": 98049,
    "HDFCBANK": 341249,
    "ASIANPAINT": 60417,
    "ULTRACEMCO": 2952193,
    "COALINDIA": 5215745,
    "POWERGRID": 3834113,
    "CIPLA": 177665,
    "HDFCLIFE": 119553,
    "WIPRO": 969473,
    "NTPC": 2977281,
    "TCS": 2953217,
    "TATACONSUM": 878593,
    "NESTLEIND": 4598529,
    "ONGC": 633601,
    "INFY": 408065,
    "TECHM": 3465729,
    "HCLTECH": 1850625,
    "NIFTY 50": 256265
}
# Access them using standard os.getenv()
USER_ID = os.getenv('USER_ID')
PASSWORD = os.getenv('PASSWORD')
ENCTOKEN = os.getenv('ENCTOKEN')
KF_SESSION = os.getenv('KF_SESSION')
PUBLIC_TOKEN = os.getenv('PUBLIC_TOKEN')
FROM_DATE = "2026-03-25"
TO_DATE = "2026-03-25"
query = {
        'user_id': USER_ID,
        'oi': "1",
        'from': FROM_DATE,
        'to': TO_DATE
            }
headers = {'authorization': f"enctoken {ENCTOKEN}"}

login_url = "https://kite.zerodha.com/api/login"
twofa_url = "https://kite.zerodha.com/api/twofa"


s = requests.Session()

def test_validity():
    global headers, query, ENCTOKEN, KF_SESSION, PUBLIC_TOKEN
    print("------------------------------------------------------------------")
    print("Enctoken:", ENCTOKEN)
    print("------------------------------------------------------------------")
    print("KF_SESSION:", KF_SESSION)
    print("------------------------------------------------------------------")
    print("PUBLIC_TOKEN:", PUBLIC_TOKEN)
    print("------------------------------------------------------------------")

    # Use a short interval for testing (30 days)
    # test_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    # test_query = query.copy()
    # test_query['from'] = test_from

    data = s.get(url='https://kite.zerodha.com/oms/instruments/historical/86529/minute', headers=headers, params=query)
    status_code = data.status_code
    print("status code from validity test:", status_code)
    if status_code != 200:
        status =data.json()['status']
        error_message = data.json()['message']
        print(f"Token validity test failed with status {status} and message: {error_message}")
        r = s.post(login_url, data={"user_id": USER_ID, "password": PASSWORD})
        j = json.loads(r.text)
        request_id = j['data']["request_id"]
        twofa_value = input('Enter 2FA value:\n')
        param = {"user_id": USER_ID, "request_id": request_id, "twofa_value": twofa_value}
        r = s.post(twofa_url, data=param)
        j = json.loads(r.text)
        my_cookies = requests.utils.dict_from_cookiejar(s.cookies)
        public_token = my_cookies['public_token']
        kf_session = my_cookies['kf_session']
        enctoken = my_cookies['enctoken']
        print("public_token:", public_token)
        print("kf_session:", kf_session)
        print("enctoken:", enctoken)


        ENCTOKEN = enctoken
        KF_SESSION = kf_session
        PUBLIC_TOKEN = public_token

        headers = {'authorization': f"enctoken {ENCTOKEN}"}

        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_lines = f.readlines()
        else:
            env_lines = []

        env_lines = [line for line in env_lines if not any(token in line for token in ['ENCTOKEN=', 'KF_SESSION=', 'PUBLIC_TOKEN='])]
        env_lines.append(f'ENCTOKEN={enctoken}\n')
        env_lines.append(f'KF_SESSION={kf_session}\n')
        env_lines.append(f'PUBLIC_TOKEN={public_token}\n')

        with open('.env', 'w') as f:
            f.writelines(env_lines)
    else:
        s.cookies.set('public_token', PUBLIC_TOKEN)
        s.cookies.set('kf_session', KF_SESSION)
        s.cookies.set('enctoken', ENCTOKEN)

TO_DATE = date.today().strftime('%Y-%m-%d')
query['to'] = TO_DATE

@st.cache_resource(show_spinner=False, ttl="6h")
def load_data(tickers, from_date, interval='day'):
        test_validity()

        # Calculate number of days requested
        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
        to_date_obj = date.today()
        days_requested = (to_date_obj - from_date_obj).days

        # If more than 5 years (1825 days), split into chunks
        main_df = None

        if days_requested > 1825:
            # Make multiple requests for 5-year chunks
            chunk_size = 1825  # 5 years
            current_from = from_date_obj

            while current_from < to_date_obj:
                chunk_to = min(current_from + timedelta(days=chunk_size), to_date_obj)
                chunk_from_str = current_from.strftime('%Y-%m-%d')
                chunk_to_str = chunk_to.strftime('%Y-%m-%d')

                print(f"Fetching chunk: {chunk_from_str} to {chunk_to_str}")
                chunk_query = query.copy()
                chunk_query['from'] = chunk_from_str
                chunk_query['to'] = chunk_to_str

                chunk_df = _fetch_chunk(tickers, chunk_query, interval, headers)

                if main_df is None:
                    main_df = chunk_df
                else:
                    main_df = pd.concat([main_df, chunk_df]).sort_index()

                current_from = chunk_to + timedelta(days=1)
        else:
            # Single request for <= 5 years
            query['from'] = from_date
            print("To_date:", query['to'], "From_date:", query['from'])
            main_df = _fetch_chunk(tickers, query, interval, headers)

        # Ensure index is date and has correct name for melt
        if main_df.index.name != 'Date':
            main_df.index.name = 'Date'

        return main_df


def _fetch_chunk(tickers, chunk_query, interval, headers):
        """Helper function to fetch data for a single chunk"""
        chunk_df = None

        for index, ticker in enumerate(tickers):
            ID = nifty_dict.get(ticker)
            print(f"Fetching data for {ticker} with ID {ID}...")
            fetch_url = 'https://kite.zerodha.com/oms/instruments/historical/{0}/{1}'.format(ID, interval)

            # Print curl command for debugging
            curl_cmd = f"curl -H 'authorization: {headers['authorization']}' '{fetch_url}?{urlencode(chunk_query)}'"
            print(f"Curl command for {ticker}: {curl_cmd}")

            response = s.get(url=fetch_url, headers=headers, params=chunk_query)
            data = response.json()
            print(f"Status Message for {ticker}:", data.get('status'), " status code: ", response.status_code)

            if data.get('status') != 'success':
                raise RuntimeError(f"Error fetching data for {ticker}: {data.get('message', 'Unknown error')}")

            y = data['data']['candles']
            df = pd.DataFrame(y)

            if index == 0:
                chunk_df = df
                chunk_df.drop(columns=[1, 2, 3, 5, 6], inplace=True)
                chunk_df.set_index(0, inplace=True)
                chunk_df.rename(columns={4: ticker}, inplace=True)
            else:
                df.drop(columns=[1, 2, 3, 5, 6], inplace=True)
                df.set_index(0, inplace=True)
                df.rename(columns={4: ticker}, inplace=True)
                chunk_df = chunk_df.join(df)

        return chunk_df


def get_pre_open_data():
    """
    Fetches pre-open market data for F&O from NSE India and returns as DataFrame.
    """
    base_url = "https://www.nseindia.com/api/market-data-pre-open"
    params = {
        'key': 'FO',
        'csv': 'true',
        'selectValFormat': 'crores'
    }
    url = f"{base_url}?{urlencode(params)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    # NSE requires establishing a session first
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # Set cookies

    try:
        response = session.get(url, headers=headers,)
        response.raise_for_status()
        print(f"Response status: {response.status_code}")
        print(f"Response content type: {response.headers.get('content-type')}")
        # print(f"First 500 chars: {response.text}")
        df = pd.read_csv(StringIO(response.text[160:]), header=None, sep=',', quotechar='"', on_bad_lines='skip')
        # Set proper column names
        columns = ['SYMBOL', 'PREV_CLOSE', 'IEP', 'CHNG', '%CHNG', 'FINAL', 'FINAL_QUANTITY', 'VALUE', 'FFM_CAP', '52W_H', '52W_L']
        df.columns = columns
        df = df.sort_values(by='VALUE', ascending=False).reset_index(drop=True)
        df = df[['SYMBOL','%CHNG', 'VALUE']]
        df["%CHNG"] = pd.to_numeric(df["%CHNG"], errors="coerce")
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")

        df_advance = df[df['%CHNG'] > 0]   # DataFrame
        df_decline = df[df['%CHNG'] < 0]   # DataFrame

        advance_count = int(df_advance.shape[0])
        decline_count = int(df_decline.shape[0])

        advance_turnover = df_advance['VALUE'].sum()
        decline_turnover = df_decline['VALUE'].sum()

        percent_advance_turnover = int(
            (advance_turnover / decline_turnover * 100)
            if decline_turnover != 0 else 0
        )
        percent_decline_turnover = int(100 - percent_advance_turnover)

        return df, advance_count, decline_count, percent_advance_turnover, percent_decline_turnover

    except Exception as e:
        print(f"Error fetching pre-open data: {str(e)}")
        print(f"Full response text: {response.text}")
        return pd.DataFrame()

def get_live_nse_data(index):
    """
    Fetches live market data for the specified index from NSE India and returns as DataFrame.
    """
    base_url = "https://www.nseindia.com/api/equity-stockIndices"
    params = {
        'index': index,  # Use the passed index parameter
        'csv': 'true',
        'selectValFormat': 'crores'
    }
    url = f"{base_url}?{urlencode(params)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    # NSE requires establishing a session first
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # Set cookies

    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        print(f"Response status: {response.status_code}")
        print(f"Response content type: {response.headers.get('content-type')}")
        # Improved parsing: use header=0 since headers are present after slice
        # print(f"First 500 chars: {response.text}")
        df = pd.read_csv(StringIO(response.text[200:]), header=None, sep=',', quotechar='"', on_bad_lines='skip')
        # Set proper column names
        columns = ['SYMBOL', 'OPEN', 'HIGH', 'LOW', 'PREV. CLOSE', 'LTP', 'INDICATIVE CLOSE', 'CHNG', '%CHNG', 'VOLUME', 'VALUE', '52W H', '52W L', '30 D %CHNG', '365 D %CHNG']
        df.columns = columns
        df = df.sort_values(by='VALUE', ascending=False).reset_index(drop=True)
        df = df[['SYMBOL','%CHNG', 'VALUE']]
        df["%CHNG"] = pd.to_numeric(df["%CHNG"], errors="coerce")
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")

        df_advance = df[df['%CHNG'] > 0] # Filter for advancing stocks
        df_decline = df[df['%CHNG'] < 0] # Filter for declining stocks
        advance_turnover = df_advance['VALUE'].sum()
        decline_turnover = df_decline['VALUE'].sum()
        percent_advance_turnover = int(advance_turnover / decline_turnover * 100) if decline_turnover != 0 else 0
        percent_decline_turnover = int(100 - percent_advance_turnover)
        df_advance =(len(df[df['%CHNG'] > 0])) # Filter for advancing stocks
        df_decline = int(len(df[df['%CHNG'] < 0])) # Filter for declining stocks
        return df,df_advance,df_decline,percent_advance_turnover,percent_decline_turnover

    except Exception as e:
        print(f"Error fetching live NSE data: {str(e)}")
        print(f"Full response text: {response.text}")
        return pd.DataFrame()


