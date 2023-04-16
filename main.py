from fastapi import FastAPI ,HTTPException
from pymongo import MongoClient
import yfinance as yf
from bson import ObjectId
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient("mongodb://localhost:27017/")
db = client["finance"]
collection = db["stocks"]

# This end point will fetch stocks from yfinance and save into our database
@app.get("/fetch_stocks/{symbol}")
def fetch_data(symbol: str):
    stock = yf.Ticker(symbol)
    data = stock.history(period="max")
    if data.empty:
        raise HTTPException(status_code=400, detail=f"No data exists for {symbol}. Try with these tickers: AAPL, META, TSLA")
    data = data.reset_index().to_dict("records")
    collection = db[symbol]
    collection.insert_many(data)
    return {"message": f"{len(data)} records fetched and saved into {symbol} collection."}

# This end point will sent stocks data from database to frontEnd
@app.get("/get_stocks/{symbol}")
def get_data(symbol: str):
    collection = db[symbol]
    data = list(collection.find({}, {'_id': 0}))
    for item in data:
        for key, value in item.items():
            if isinstance(value, ObjectId):
                item[key] = str(value)
    return {"symbol": symbol, "data": data}

# This end point will sent tickers symbol list avaliable in database
@app.get("/stocks_in_db")
def get_collections():
    stocks = db.list_collection_names()
    return {"stocks": stocks}


scheduler = BackgroundScheduler()

def fetch_stocks(symbols: list):
    for symbol in symbols:
        url = f"http://localhost:8000/fetch_stocks/{symbol}"
        response = requests.get(url)
        print(response.json())

def fetch_stocks_dynamic():
    # Get the list of tickers from the endpoint
    tickers_url = "http://localhost:8000/stocks_in_db" 
    tickers_response = requests.get(tickers_url)
    tickers_data = tickers_response.json()
    symbols = tickers_data["stocks"]

    # Fetch data for each ticker
    for symbol in symbols:
        url = f"http://localhost:8000/fetch_stocks/{symbol}"
        response = requests.get(url)
        print(response.json())

symbols1 = ["AMZN", "MSFT", "GOOG", "TSLA", "AAPL"]
scheduler.add_job(fetch_stocks, "interval", seconds=60, args=[symbols1])
scheduler.add_job(fetch_stocks_dynamic, "cron", hour=0)

scheduler.start()
