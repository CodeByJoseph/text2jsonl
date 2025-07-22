import os
import json

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_database_files(data_dir="database"):
    """Get database files without extensions"""
    files = [f for f in os.listdir(data_dir) if f.endswith(".jsonl")]
    return [os.path.splitext(f)[0] for f in files]

def load_cached_results(db_name):
    cache_file = os.path.join(CACHE_DIR, db_name + "_results.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_cached_results(db_name, results):
    cache_file = os.path.join(CACHE_DIR, db_name + "_results.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
