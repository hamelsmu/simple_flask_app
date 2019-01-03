"this file imports all of the data in books.csv into the postgres database hosted on Heroku."
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import ipdb
import pandas as pd
from tqdm import tqdm
import json

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

data = json.loads(pd.read_csv('books.csv').to_json(orient='records'))

for row in tqdm(data, total=len(data)):
    db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                   dict(row))

test = db.execute("SELECT * FROM books").fetchall()
print(f'{len(test)} rows added to the table book_users')