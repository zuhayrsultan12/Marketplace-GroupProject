import sqlite3
# testing and setting up barebones
# connect to database
conn = sqlite3.connect('student_market.db')
cursor = conn.cursor()

# insert a fake item to new table
# seller_id, title, price, location, category
cursor.execute("""
    INSERT INTO items (seller_id, title, price, location, category) 
    VALUES (?, ?, ?, ?, ?)
""", (1, 'Calculus Textbook', 20.0, 'University of Brighton', 'Books'))

conn.commit()
conn.close()
print("✅ Fake item added successfully!")