from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')

for dbname in ['beatvegas', 'beatvegas_db', 'permutation_carlos_db']:
    db = client[dbname]
    print(f'\n{dbname}:')
    print(f'  user_bets: {db.user_bets.count_documents({})}')
    print(f'  api_keys: {db.api_keys.count_documents({})}')
    print(f'  prediction_logs: {db.prediction_logs.count_documents({})}')
    print(f'  parlay_analysis: {db.parlay_analysis.count_documents({})}')
    print(f'  simulations: {db.monte_carlo_simulations.count_documents({})}')
    
    sims = list(db.monte_carlo_simulations.find().limit(1))
    if sims:
        print(f'  Simulation has "sport": {"sport" in sims[0]}')
        print(f'  Simulation has "sport_key": {"sport_key" in sims[0]}')
