import vecs
import os

connection_string = "postgresql://postgres.chskrfrnjdeedendqzhc:YDGjTqHaB3QeC8GV@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres"
vx = vecs.create_client(connection_string)

try:
    collection = vx.get_collection("gets_travel_vectors")
    # Query with dummy 384d vector (assuming fastembed was used)
    response = collection.query(
        data=[0.0] * 384,
        limit=2,
        include_metadata=True,
        include_value=True,
        measure="cosine_distance"
    )
    
    print("RESULTS LENGTH:", len(response))
    for r in response:
        print("TYPE:", type(r))
        print("CONTENTS:", r)
except Exception as e:
    print("ERROR:", e)
