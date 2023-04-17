from fastapi import FastAPI ,HTTPException
from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient
import yfinance as yf
from datetime import datetime
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import requests

api_url = os.getenv('API')
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(os.getenv("MONGO"))
db = client["finance"]
collection = db["stocks"]

# This end point will fetch stocks from yfinance and save into our database
@app.get("/fetch_stocks/{symbol}")
def fetch_data(symbol: str):
    stock = yf.Ticker(symbol)
    collection = db[symbol]
    last_record = collection.find_one(sort=[("Date", -1)])
    if last_record:
        last_date = last_record["Date"].strftime("%Y-%m-%d")
        data = stock.history(start=last_date)
    else:
        data = stock.history(period="max")
    if data.empty:
        raise HTTPException(status_code=400, detail=f"No new data exists for {symbol}. Try with these tickers: AAPL, META, TSLA")
    data = data.reset_index().to_dict("records")
    collection.insert_many(data)
    return {"message": f"{len(data)} new records fetched and saved into {symbol} collection."}

# This end point will sent stocks data from our database to frontEnd
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

# scheduler to fetch data and save in database
scheduler = BackgroundScheduler()

def fetch_stocks(symbols: list):
    for symbol in symbols:
        url = f"{api_url}/fetch_stocks/{symbol}"
        response = requests.get(url)
        print(response.json())

def fetch_stocks_dynamic():
    # Get the list of tickers from our database
    tickers_url = f"{api_url}/stocks_in_db" 
    tickers_response = requests.get(tickers_url)
    tickers_data = tickers_response.json()
    symbols = tickers_data["stocks"]

    # Fetch ticker data for each in our database
    for symbol in symbols:
        url = f"{api_url}/fetch_stocks/{symbol}"
        response = requests.get(url)
        print(response.json())

symbols1 = ["AMZN", "MSFT", "GOOG", "TSLA", "AAPL"]
scheduler.add_job(fetch_stocks, "interval", seconds=60, args=[symbols1])
scheduler.add_job(fetch_stocks_dynamic, "cron", hour=0)

scheduler.start()
