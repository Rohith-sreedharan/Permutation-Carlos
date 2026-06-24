#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')
from db.mongo import db

print('DAILY_BEST_CARDS numeric odds >= 900')
for v in db.daily_best_cards.aggregate([
    {'$match': {'odds': {'$type': 'number'}}},
    {'$group': {'_id': '$odds', 'count': {'$sum': 1}}},
    {'$match': {'_id': {'$gte': 900}}},
    {'$sort': {'_id': 1}},
    {'$limit': 200},
]):
    print(v['_id'], v['count'])

print('\nSIMULATIONS outcome.odds >= 900')
for v in db.monte_carlo_simulations.aggregate([
    {'$match': {'outcome.odds': {'$type': 'number'}}},
    {'$group': {'_id': '$outcome.odds', 'count': {'$sum': 1}}},
    {'$match': {'_id': {'$gte': 900}}},
    {'$sort': {'_id': 1}},
    {'$limit': 500},
]):
    print(v['_id'], v['count'])

print('\nCOUNT outcome.odds == 999:', db.monte_carlo_simulations.count_documents({'outcome.odds': 999}))
print('COUNT outcome.odds == 9999:', db.monte_carlo_simulations.count_documents({'outcome.odds': 9999}))
print('COUNT outcome.odds == 1300:', db.monte_carlo_simulations.count_documents({'outcome.odds': 1300}))
print('COUNT outcome.odds == 2000:', db.monte_carlo_simulations.count_documents({'outcome.odds': 2000}))
print('COUNT outcome.odds == 2200:', db.monte_carlo_simulations.count_documents({'outcome.odds': 2200}))
