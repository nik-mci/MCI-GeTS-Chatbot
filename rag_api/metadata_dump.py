from utils.vector_db import get_vector_db
db = get_vector_db()
for i in range(5):
    print(f"Index {i}: {db.metadata[i]}")
