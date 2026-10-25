from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, timedelta
import re
import secrets

app = Flask(__name__)
app.secret_key = 'super_secret_student_market_key'
app.config['SESSION_PERMANENT'] = False
app.permanent_session_lifetime = timedelta(minutes=30)


def get_db_connection():
    # finds the exact folder where app.py is currently sitting
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'student_market.db')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_checkout_tables():
    # ZS Adds missing order columns safely when the app starts or runs against an old database.
    conn = get_db_connection()
    cursor = conn.cursor()

    # ZS Creates the order table if the database is new.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            item_id INTEGER,
            seller_id INTEGER,
            item_title TEXT NOT NULL,
            price REAL NOT NULL,
            transaction_id TEXT,
            status TEXT DEFAULT 'Payment confirmed',
            delivery_method TEXT,
            shipping_address TEXT,
            payment_method TEXT,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users (id),
            FOREIGN KEY (item_id) REFERENCES items (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    ''')

    # ZS Adds columns to an existing order table without deleting the old order history.
    existing_order_columns = [row[1] for row in cursor.execute("PRAGMA table_info(orders)").fetchall()]
    order_columns_to_add = {
        'item_id': 'INTEGER',
        'seller_id': 'INTEGER',
        'transaction_id': 'TEXT',
        'status': "TEXT DEFAULT 'Payment confirmed'",
        'delivery_method': 'TEXT',
        'shipping_address': 'TEXT',
        'payment_method': 'TEXT',
        'last_updated': 'TIMESTAMP'
    }

    for column_name, column_type in order_columns_to_add.items():
        if column_name not in existing_order_columns:
            cursor.execute(f'ALTER TABLE orders ADD COLUMN {column_name} {column_type}')

    # ZS Fills last_updated for older rows because SQLite cannot add a CURRENT_TIMESTAMP default using ALTER TABLE.
    cursor.execute('UPDATE orders SET last_updated = CURRENT_TIMESTAMP WHERE last_updated IS NULL')

    # ZS Adds the sold tracking to items so purchased listings will get removed from the marketplace.
    existing_item_columns = [row[1] for row in cursor.execute("PRAGMA table_info(items)").fetchall()]
    if 'is_sold' not in existing_item_columns:
        cursor.execute('ALTER TABLE items ADD COLUMN is_sold INTEGER DEFAULT 0')
    if 'sold_to' not in existing_item_columns:
        cursor.execute('ALTER TABLE items ADD COLUMN sold_to INTEGER')

    # ZS Creates the reviews table if it does not already exist.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            order_id INTEGER,
            item_id INTEGER,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reviewer_id) REFERENCES users (id),
            FOREIGN KEY (target_user_id) REFERENCES users (id),
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    ''')

    # ZS Adds order_id and item_id to old review tables so one review can be linked to one bought item.
    existing_review_columns = [row[1] for row in cursor.execute("PRAGMA table_info(reviews)").fetchall()]
    if 'order_id' not in existing_review_columns:
        cursor.execute('ALTER TABLE reviews ADD COLUMN order_id INTEGER')
    if 'item_id' not in existing_review_columns:
        cursor.execute('ALTER TABLE reviews ADD COLUMN item_id INTEGER')

    conn.commit()
    conn.close()


ensure_checkout_tables()


@app.route('/')
def index():
    conn = get_db_connection()

    # matches created in init_db.py
    category_filter = request.args.get('category')
    Price_Filter = request.args.get('price')
    Location_Filter = request.args.get("location")
    Search_Fil = request.args.get("search")

    print("Price filter selected:", Price_Filter)
    print("location filter seleceted:", Location_Filter)
    print("search selected:", Search_Fil) 

    query = 'SELECT * FROM items WHERE is_sold = 0'
    params = []

    if category_filter:
        query += ' AND category = ?'
        params.append(category_filter)

    if Price_Filter == '0-50':
        query += ' AND price >= ? AND price < ?'
        params.extend([0, 50])
    elif Price_Filter == '50-100':
        query += ' AND price >= ? AND price < ?'
        params.extend([50, 100])
    elif Price_Filter == '100-200':
        query += ' AND price >= ? AND price < ?'
        params.extend([100, 200])
    elif Price_Filter == '200-plus':
        query += ' AND price >= ?'
        params.append(200)

    if Location_Filter:
        query += ' AND LOWER(TRIM(location)) = LOWER(TRIM(?))'
        params.append(Location_Filter)    

    if Search_Fil:
        query += " AND LOWER(title) LIKE LOWER(?)"
        params.append("%" + Search_Fil + "%")    

    query += ' ORDER BY id DESC'
    print("QUERY:", query)
    print("PARAMS:", params)

    items = conn.execute(query, params).fetchall()



    conn.close()
    return render_template('index.html', items=items, current_category=category_filter, current_price=Price_Filter, current_location=Location_Filter, current_search=Search_Fil)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print("🚨 WHAT THE BROWSER SENT:", request.form)

        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        university = request.form['university']
        location = request.form['location']
        recovery_question = request.form['recovery_question']
        recovery_answer = request.form['recovery_answer']

        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return redirect(url_for('register'))

        if not re.search(r"[A-Z]", password):
            flash('Password must contain at least one uppercase letter')
            return redirect(url_for('register'))

        if not re.search(r"[0-9]", password):
            flash('Password must contain at least one number')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        q = request.form['recovery_question']
        a = request.form['recovery_answer']

        conn = get_db_connection()

        try:
            conn.execute(
                '''
                INSERT INTO users (
                    full_name, email, password, university, location,
                    recovery_question, recovery_answer
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (full_name, email, hashed_password, university, location, q, a)
            )
            conn.commit()
            conn.close()

            # If successful, send them to login
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            conn.close()
            return "Error: Email already registered."

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if not user:
            flash('Invalid email or password')
            conn.close()
            return redirect(url_for('login'))

        if user['locked_until']:
            locked_time = datetime.strptime(user['locked_until'], '%Y-%m-%d %H:%M:%S')

            if datetime.now() < locked_time:
                time_left = (locked_time - datetime.now()).seconds // 60 + 1
                flash(f'Account locked due to too many failed attempts. Try again in {time_left} minutes')
                conn.close()
                return redirect(url_for('login'))

            conn.execute(
                'UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?',
                (user['id'],)
            )
            conn.commit()

        # testing for terminal output
        print(f"DEBUG: Typed password is: {password}")
        print(f"DEBUG: Database password is: {user['password']}")

        if check_password_hash(user['password'], password):
            # reset failed attempts
            conn.execute(
                'UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?',
                (user['id'],)
            )
            conn.commit()
            conn.close()

            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']

            return redirect(url_for('index'))

        # incorrect password attempt value
        attempts = user['failed_attempts'] + 1

        if attempts >= 5:
            # locks account for 10 minutes
            lock_time = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                'UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?',
                (attempts, lock_time, user['id'])
            )
            flash('Account locked for 10 minutes due to too many failed attempts.')
        else:
            # warn user
            conn.execute(
                'UPDATE users SET failed_attempts = ? WHERE id = ?',
                (attempts, user['id'])
            )
            flash(f'Invalid credentials. {5 - attempts} attempts remaining.')

        conn.commit()
        conn.close()
        return redirect(url_for('login'))

    # show the login form
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # fetches users full row
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    # fetches items user is selling
    items = conn.execute(
        'SELECT * FROM items WHERE seller_id = ? AND is_sold = 0',
        (session['user_id'],)
    ).fetchall()

    # ZS Fetches the buyer's order history with item and seller details.
    orders = conn.execute('''
        SELECT orders.*, users.full_name AS seller_name
        FROM orders
        LEFT JOIN users ON orders.seller_id = users.id
        WHERE orders.buyer_id = ?
        ORDER BY orders.purchase_date DESC
    ''', (session['user_id'],)).fetchall()

    # ZS Fetches sale transactions so sellers can view and update their transaction status.
    sales_orders = conn.execute('''
        SELECT orders.*, users.full_name AS buyer_name
        FROM orders
        LEFT JOIN users ON orders.buyer_id = users.id
        WHERE orders.seller_id = ?
        ORDER BY orders.purchase_date DESC
    ''', (session['user_id'],)).fetchall()

    reviews = conn.execute('''
        SELECT reviews.*, users.full_name AS reviewer_name
        FROM reviews
        JOIN users ON reviews.reviewer_id = users.id
        WHERE target_user_id = ?
        ORDER BY reviews.id DESC
    ''', (session['user_id'],)).fetchall()

    # ZS Calculates this user's average seller rating from all reviews they received.
    rating_summary = conn.execute('''
        SELECT AVG(rating) AS average_rating, COUNT(*) AS review_count
        FROM reviews
        WHERE target_user_id = ?
    ''', (session['user_id'],)).fetchone()

    conn.close()

    # pass objects to html
    return render_template(
        'profile.html',
        user=user,
        items=items,
        orders=orders,
        sales_orders=sales_orders,
        reviews=reviews,
        rating_summary=rating_summary
    )


@app.route('/update_account', methods=['POST'])
def update_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    full_name = request.form.get('full_name')
    address = request.form.get('address')
    payment_info = request.form.get('payment_info')
    university = request.form.get('university')

    conn = get_db_connection()
    conn.execute('''
        UPDATE users 
        SET full_name = ?, address = ?, payment_info = ?, university = ?
        WHERE id = ?
    ''', (full_name, address, payment_info, university, session['user_id']))

    conn.commit()
    conn.close()

    session['user_name'] = full_name  # update session if name changed

    flash('Account settings updated!')
    return redirect(url_for('profile'))


@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    old_pw = request.form['old_password']
    new_pw = request.form['new_password']
    confirm_pw = request.form['confirm_new_password']

    conn = get_db_connection()
    user = conn.execute(
        'SELECT password FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    # verify old password is correct
    if not check_password_hash(user['password'], old_pw):
        conn.close()
        flash('Error: Current password incorrect.')
        return redirect(url_for('profile'))

    # verify new passwords match
    if new_pw != confirm_pw:
        conn.close()
        flash('Error: New passwords do not match.')
        return redirect(url_for('profile'))

    # success, update password
    hashed_password = generate_password_hash(new_pw)

    conn.execute(
        'UPDATE users SET password = ? WHERE id = ?',
        (hashed_password, session['user_id'])
    )

    conn.commit()
    conn.close()

    flash('Password updated successfully!')
    return redirect(url_for('profile'))


@app.route('/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form.get('email')
        answer = request.form.get('recovery_answer')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_new_password')

        conn = get_db_connection()

        # findthe user by email
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        ).fetchone()

        # check if user exists and the answer matches
        if not user or user['recovery_answer'] != answer:
            conn.close()
            flash("Error: Recovery details do not match.")
            return redirect(url_for('recover'))

        # check new passwords match
        if new_pw != confirm_pw:
            conn.close()
            flash("Error: New passwords do not match.")
            return redirect(url_for('recover'))

        # if success update the password
        hashed_pw = generate_password_hash(new_pw)

        conn.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (hashed_pw, user['id'])
        )

        conn.commit()
        conn.close()

        flash("Password has been reset. You can now log in.")
        return redirect(url_for('login'))

    return render_template('recover.html')


@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()

    # used a join to get the sellers name along with item info
    query = '''
        SELECT items.*, users.full_name as seller_name 
        FROM items 
        JOIN users ON items.seller_id = users.id 
        WHERE items.id = ?
    '''

    item = conn.execute(query, (item_id,)).fetchone()

    if item is None:
        conn.close()
        return "Item not found", 404

    # ZS Gets the seller's average rating so buyers can see seller reputation before checkout.
    seller_rating = conn.execute('''
        SELECT AVG(rating) AS average_rating, COUNT(*) AS review_count
        FROM reviews
        WHERE target_user_id = ?
    ''', (item['seller_id'],)).fetchone()

    conn.close()

    return render_template('item_detail.html', item=item, seller_rating=seller_rating)


@app.route('/post_item', methods=['GET', 'POST'])
def post_item():
    # kicks unauthorized users immediately
    if 'user_id' not in session:
        flash('You must be logged in to sell an item.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # safely capture form data
        title = request.form.get('title')
        price = request.form.get('price')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')

        # verify required fields arent blank
        if not title or not price or not category or not location:
            flash('Error: Please fill out all required fields.')
            return redirect(url_for('post_item'))

        conn = get_db_connection()

        try:
            # parameterized query to prevent SQL Injection
            # note: We pull seller_id directly from the session
            conn.execute('''
                INSERT INTO items (
                    seller_id, title, price, location, category, description
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], title, float(price), location, category, description))

            conn.commit()
            flash('Done, Your item is now on the marketplace.')

        except Exception as e:
            flash('A database error occurred. Please try again.')
            print(f"DB Error: {e}")

        finally:
            conn.close()

        # send them back to their profile to see the new active listing
        return redirect(url_for('profile'))

    # if its a GET request, just show the form
    return render_template('post_item.html')


@app.route('/checkout/<int:item_id>', methods=['GET', 'POST'])
def checkout(item_id):
    # ZS Sends guests to the login page before they can use the checkout.
    if 'user_id' not in session:
        flash('Please log in before checkout.')
        return redirect(url_for('login'))

    conn = get_db_connection()

    item = conn.execute('''
        SELECT items.*, users.full_name AS seller_name
        FROM items
        JOIN users ON items.seller_id = users.id
        WHERE items.id = ?
    ''', (item_id,)).fetchone()

    # ZS Stops the checkout if the item is out of stock / longer exists.
    if item is None:
        conn.close()
        flash('Item not found.')
        return redirect(url_for('index'))

    # ZS Stops users from buying their own listings.
    if item['seller_id'] == session['user_id']:
        conn.close()
        flash('You cannot buy your own item.')
        return redirect(url_for('item_detail', item_id=item_id))

    # ZS Stops checkout if another buyer has already bought the item.
    if item['is_sold']:
        conn.close()
        flash('This item has already been sold.')
        return redirect(url_for('item_detail', item_id=item_id))

    if request.method == 'POST':
        delivery_method = request.form.get('delivery_method')
        shipping_address = request.form.get('shipping_address')
        payment_method = request.form.get('payment_method')
        card_name = request.form.get('card_name')
        card_number = request.form.get('card_number', '').replace(' ', '')

        # ZS Validates the mock checkout form before creating the order.
        if not delivery_method or not shipping_address or not payment_method or not card_name or not card_number:
            conn.close()
            flash('Please complete every field.')
            return redirect(url_for('checkout', item_id=item_id))

        # ZS The payments are fake but still checks that the mock card number looks realistic.
        if not card_number.isdigit() or len(card_number) < 12:
            conn.close()
            flash('Use a card number with at least 12 digits.')
            return redirect(url_for('checkout', item_id=item_id))

        transaction_id = 'TXN-' + datetime.now().strftime('%Y%m%d%H%M%S') + '-' + secrets.token_hex(3).upper()
        safe_payment_label = payment_method + ' ending ' + card_number[-4:]

        # ZS Creates the order and marks the item as sold in one commit.
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders (
                buyer_id, item_id, seller_id, item_title, price, transaction_id,
                status, delivery_method, shipping_address, payment_method
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            item['id'],
            item['seller_id'],
            item['title'],
            item['price'],
            transaction_id,
            'Payment confirmed',
            delivery_method,
            shipping_address,
            safe_payment_label
        ))

        order_id = cursor.lastrowid

        cursor.execute(
            'UPDATE items SET is_sold = 1, sold_to = ? WHERE id = ?',
            (session['user_id'], item_id)
        )

        conn.commit()
        conn.close()

        flash('Checkout complete. Your transaction has been processed.')
        return redirect(url_for('transaction_status', order_id=order_id))

    conn.close()
    return render_template('checkout.html', item=item)


@app.route('/transaction/<int:order_id>')
def transaction_status(order_id):
    # ZS Requires login before showing the user private transaction information.
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    order = conn.execute('''
        SELECT orders.*, buyer.full_name AS buyer_name, seller.full_name AS seller_name
        FROM orders
        LEFT JOIN users AS buyer ON orders.buyer_id = buyer.id
        LEFT JOIN users AS seller ON orders.seller_id = seller.id
        WHERE orders.id = ?
    ''', (order_id,)).fetchone()

    # ZS Only the buyer or seller can view the transaction.
    if order is None or (order['buyer_id'] != session['user_id'] and order['seller_id'] != session['user_id']):
        conn.close()
        flash('Transaction not found.')
        return redirect(url_for('profile'))

    existing_review = None

    # ZS Checks whether this buyer has already reviewed this exact bought item.
    if session['user_id'] == order['buyer_id']:
        existing_review = conn.execute('''
            SELECT *
            FROM reviews
            WHERE reviewer_id = ? AND item_id = ?
        ''', (session['user_id'], order['item_id'])).fetchone()

    conn.close()

    return render_template(
        'transaction_status.html',
        order=order,
        existing_review=existing_review
    )


@app.route('/update_transaction_status/<int:order_id>', methods=['POST'])
def update_transaction_status(order_id):
    # ZS Requires login before a seller can update the transaction progress.
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_status = request.form.get('status')

    allowed_statuses = [
        'Payment confirmed',
        'Seller preparing item',
        'Ready for collection',
        'Dispatched',
        'Completed',
        'Cancelled'
    ]

    # ZS Blocks any unknown status values so the database only stores expected transaction states.
    if new_status not in allowed_statuses:
        flash('Invalid transaction status.')
        return redirect(url_for('profile'))

    conn = get_db_connection()

    order = conn.execute(
        'SELECT * FROM orders WHERE id = ?',
        (order_id,)
    ).fetchone()

    # ZS Only the seller of the item can update the transaction status.
    if order is None or order['seller_id'] != session['user_id']:
        conn.close()
        flash('You can only update transactions for your own sales.')
        return redirect(url_for('profile'))

    conn.execute(
        'UPDATE orders SET status = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?',
        (new_status, order_id)
    )

    conn.commit()
    conn.close()

    flash('Transaction status updated.')
    return redirect(url_for('transaction_status', order_id=order_id))


@app.route('/submit_review/<int:order_id>', methods=['POST'])
def submit_review(order_id):
    # ZS Requires the user to be logged in before submitting a seller review.
    if 'user_id' not in session:
        return redirect(url_for('login'))

    rating = request.form.get('rating')
    comment = request.form.get('comment')
    reviewer_id = session['user_id']

    conn = get_db_connection()

    # ZS Finds the paid order so reviews can only happen after checkout/payment.
    order = conn.execute('''
        SELECT *
        FROM orders
        WHERE id = ? AND buyer_id = ?
    ''', (order_id, reviewer_id)).fetchone()

    # ZS Blocks reviews unless the logged-in user actually paid for this order.
    if order is None:
        conn.close()
        flash('You can only review a seller after completing payment.')
        return redirect(url_for('profile'))

    target_id = order['seller_id']
    item_id = order['item_id']

    # ZS Stops users from reviewing themselves.
    if reviewer_id == target_id:
        conn.close()
        flash("You can't review yourself!")
        return redirect(url_for('profile'))

    # ZS Prevents duplicate reviews for the same bought item while still allowing reviews for other items from the same seller.
    existing_review = conn.execute('''
        SELECT id
        FROM reviews
        WHERE reviewer_id = ? AND item_id = ?
    ''', (reviewer_id, item_id)).fetchone()

    if existing_review:
        conn.close()
        flash('You have reviewed this item purchase.')
        return redirect(url_for('transaction_status', order_id=order_id))

    # ZS Saves the review with the order and item so the same seller can be reviewed again for another purchase.
    conn.execute('''
        INSERT INTO reviews (
            reviewer_id, target_user_id, order_id, item_id, rating, comment
        )
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (reviewer_id, target_id, order_id, item_id, rating, comment))

    conn.commit()
    conn.close()

    flash('Review submitted!')
    return redirect(url_for('transaction_status', order_id=order_id))


@app.route('/test_review')
def test_review():
    if 'user_id' not in session:
        return "Log in first!"

    conn = get_db_connection()

    # This creates a 5-star review for YOU, from "Reviewer ID 1" usually the first user
    conn.execute('''
        INSERT INTO reviews (
            reviewer_id, target_user_id, rating, comment
        )
        VALUES (?, ?, ?, ?)
    ''', (1, session['user_id'], 5, "Johnny is a top seller. Item was exactly as described!"))

    conn.commit()
    conn.close()

    return "Review added! Go check your profile."


if __name__ == '__main__':
    app.run(debug=True)