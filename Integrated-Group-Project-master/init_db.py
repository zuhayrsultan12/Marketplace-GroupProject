import sqlite3

def init_db():
    conn = sqlite3.connect('student_market.db')
    cursor = conn.cursor()

    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            university TEXT NOT NULL,
            location TEXT NOT NULL,
            recovery_question TEXT NOT NULL,
            recovery_answer TEXT NOT NULL,
            payment_info TEXT,
            address TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT
        )
    ''')

    #ORDERS TABLE 
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        item_title TEXT NOT NULL,
        price REAL NOT NULL,
        purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (buyer_id) REFERENCES users (id)
    )
''')

    # . ITEMS TABLE (Tom)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            location TEXT NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT DEFAULT 'default.jpg',
            description TEXT,
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    ''')

    # . CONVERSATIONS TABLE (Zuhayr)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            FOREIGN KEY (item_id) REFERENCES items (id),
            FOREIGN KEY (buyer_id) REFERENCES users (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    ''')

    # . MESSAGES TABLE (Zuhayr)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (sender_id) REFERENCES users (id)
        )
    ''')
    
    #reviews
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            university TEXT NOT NULL,
            location TEXT NOT NULL,
            recovery_question TEXT NOT NULL,
            recovery_answer TEXT NOT NULL,
            payment_info TEXT,
            address TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            is_admin INTEGER DEFAULT 0  -- Add this line!
        )
    ''')

    conn.commit()
    conn.close()
    print("Database successfully created: student_market.db")

if __name__ == '__main__':
    init_db()