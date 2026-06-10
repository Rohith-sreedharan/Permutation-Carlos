#!/usr/bin/env python3
from pymongo import MongoClient
import requests

client=MongoClient('mongodb://localhost:27017')
db=client['beatvegas']

print('event count', db.events.count_documents({}))
print('simulation count', db.monte_carlo_simulations.count_documents({}))

for ev in db.events.find({}, {'event_id':1,'sport_key':1,'home_team':1,'away_team':1}).limit(10):
    print(ev)
