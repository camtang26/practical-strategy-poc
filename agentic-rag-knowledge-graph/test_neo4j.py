from neo4j import GraphDatabase
import os

uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "agpassword123")

print(f"Testing connection to: {uri}")
print(f"User: {user}")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1 AS num")
        record = result.single()
        print(f"Success! Got: {record['num']}")
    driver.close()
except Exception as e:
    print(f"Error: {e}")
