import sqlite3
import hashlib
from datetime import datetime, date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import DateEntry

DB = "hotel.db"

# ---------------------------
# Database utilities
# ---------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS Rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE,
        room_type TEXT,
        price_per_night REAL,
        status TEXT DEFAULT 'Available', 
        description TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS Customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password_hash TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS Bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        room_id INTEGER,
        check_in DATE,
        check_out DATE,
        status TEXT DEFAULT 'Pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES Customers(customer_id),
        FOREIGN KEY(room_id) REFERENCES Rooms(room_id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS Payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER,
        amount REAL,
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        payment_mode TEXT,
        FOREIGN KEY(booking_id) REFERENCES Bookings(booking_id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS Staff (
        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password_hash TEXT
    )""")
    conn.commit()
    conn.close()

def seed_data():
    conn = get_db()
    c = conn.cursor()
    # Create sample admin staff if not exists
    c.execute("SELECT * FROM Staff WHERE email = ?", ("admin@hotel",))
    if not c.fetchone():
        pw = hash_password("admin123")
        c.execute("INSERT INTO Staff (name,role,email,phone,password_hash) VALUES (?,?,?,?,?)",
                  ("Admin", "Manager", "admin@hotel", "0000000000", pw))
    # Create sample rooms if table empty
    c.execute("SELECT COUNT(*) as cnt FROM Rooms")
    if c.fetchone()["cnt"] == 0:
        rooms = [
            ("101", "Single", 1500.0, "Available", "Cozy single bed with AC and WiFi"),
            ("102", "Double", 2500.0, "Available", "Double bed with sea view and balcony"),
            ("103", "Single", 1600.0, "Available", "Single bed with garden view"),
            ("201", "Suite", 5000.0, "Available", "Luxury suite with living area and kitchen"),
            ("202", "Double", 2600.0, "Available", "Double bed with city view and balcony"),
            ("203", "Suite", 4800.0, "Available", "Executive suite with workspace"),
            ("301", "Double", 2400.0, "Available", "Double bed with pool view"),
            ("302", "Single", 1550.0, "Available", "Compact single room with all amenities"),
        ]
        for r in rooms:
            c.execute("INSERT INTO Rooms (room_number,room_type,price_per_night,status,description) VALUES (?,?,?,?,?)", r)
    conn.commit()
    conn.close()

# ---------------------------
# Helpers
# ---------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def parse_date(s: str):
    """Parse date in DD-MM-YYYY format"""
    try:
        return datetime.strptime(s, "%d-%m-%Y").date()
    except Exception:
        return None

def format_date(d):
    """Format date to DD-MM-YYYY"""
    if isinstance(d, str):
        # If it's stored as YYYY-MM-DD in DB, convert it
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            return dt.strftime("%d-%m-%Y")
        except:
            return d
    elif isinstance(d, date):
        return d.strftime("%d-%m-%Y")
    return str(d)

def dates_overlap(a_start, a_end, b_start, b_end):
    """Check if two date ranges overlap (inclusive)"""
    return not (a_end <= b_start or b_end <= a_start)

# ---------------------------
# Business logic
# ---------------------------
def check_availability(room_id, check_in, check_out):
    """Return True if room is available for the date range."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM Bookings 
        WHERE room_id = ? AND status IN ('Pending', 'Confirmed')
        """, (room_id,))
    rows = c.fetchall()
    conn.close()
    
    for r in rows:
        b_in = datetime.strptime(r["check_in"], "%Y-%m-%d").date()
        b_out = datetime.strptime(r["check_out"], "%Y-%m-%d").date()
        if dates_overlap(check_in, check_out, b_in, b_out):
            return False
    return True

def find_available_rooms(check_in, check_out, room_type=None):
    """Find available rooms for given date range and optional room type filter."""
    conn = get_db()
    c = conn.cursor()
    
    if room_type and room_type != "All":
        c.execute("SELECT * FROM Rooms WHERE status != 'Maintenance' AND room_type = ?", (room_type,))
    else:
        c.execute("SELECT * FROM Rooms WHERE status != 'Maintenance'")
    
    rooms = c.fetchall()
    conn.close()
    
    available = []
    for r in rooms:
        if check_availability(r["room_id"], check_in, check_out):
            available.append(r)
    return available

def create_booking(customer_id, room_id, check_in, check_out):
    """Create a new booking."""
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO Bookings (customer_id, room_id, check_in, check_out, status) VALUES (?,?,?,?,?)",
              (customer_id, room_id, check_in.isoformat(), check_out.isoformat(), "Pending"))
    booking_id = c.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def record_payment(booking_id, amount, mode):
    """Record a payment and update booking status."""
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO Payments (booking_id, amount, payment_mode) VALUES (?,?,?)",
              (booking_id, amount, mode))
    c.execute("UPDATE Bookings SET status = 'Confirmed' WHERE booking_id = ?", (booking_id,))
    conn.commit()
    conn.close()

def get_dashboard_stats():
    """Get statistics for admin dashboard."""
    conn = get_db()
    c = conn.cursor()
    
    stats = {}
    
    # Total rooms
    c.execute("SELECT COUNT(*) as cnt FROM Rooms")
    stats['total_rooms'] = c.fetchone()['cnt']
    
    # Available rooms
    c.execute("SELECT COUNT(*) as cnt FROM Rooms WHERE status = 'Available'")
    stats['available_rooms'] = c.fetchone()['cnt']
    
    # Total bookings
    c.execute("SELECT COUNT(*) as cnt FROM Bookings")
    stats['total_bookings'] = c.fetchone()['cnt']
    
    # Pending bookings
    c.execute("SELECT COUNT(*) as cnt FROM Bookings WHERE status = 'Pending'")
    stats['pending_bookings'] = c.fetchone()['cnt']
    
    # Confirmed bookings
    c.execute("SELECT COUNT(*) as cnt FROM Bookings WHERE status = 'Confirmed'")
    stats['confirmed_bookings'] = c.fetchone()['cnt']
    
    # Total revenue
    c.execute("SELECT SUM(amount) as total FROM Payments")
    result = c.fetchone()
    stats['total_revenue'] = result['total'] if result['total'] else 0
    
    conn.close()
    return stats

# ---------------------------
# GUI
# ---------------------------

class HotelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hotel Booking System")
        self.geometry("1000x650")
        self.resizable(False, False)
        
        # Color scheme
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'danger': '#e74c3c',
            'warning': '#f39c12',
            'light': '#ecf0f1',
            'dark': '#34495e'
        }
        
        self.configure(bg=self.colors['light'])
        
        self.user = None
        self.staff = None

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)
        
        # Configure styles
        self.setup_styles()
        
        self.show_welcome()

    def setup_styles(self):
        """Setup custom ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure button styles
        style.configure('Primary.TButton', 
                       background=self.colors['secondary'],
                       foreground='white',
                       padding=10,
                       font=('Arial', 10, 'bold'))
        
        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground='white',
                       padding=8)
        
        style.configure('Danger.TButton',
                       background=self.colors['danger'],
                       foreground='white',
                       padding=8)
        
        # Configure treeview
        style.configure('Treeview',
                       background='white',
                       foreground='black',
                       rowheight=25,
                       fieldbackground='white')
        style.map('Treeview', background=[('selected', self.colors['secondary'])])

    def clear(self):
        """Clear all widgets from main frame."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def create_header(self, text, subtitle=""):
        """Create a styled header."""
        header_frame = tk.Frame(self.main_frame, bg=self.colors['primary'], height=80)
        header_frame.pack(fill="x", pady=(0, 10))
        header_frame.pack_propagate(False)
        
        title = tk.Label(header_frame, text=text, 
                        font=("Arial", 24, "bold"),
                        bg=self.colors['primary'],
                        fg='white')
        title.pack(pady=(15, 0))
        
        if subtitle:
            sub = tk.Label(header_frame, text=subtitle,
                          font=("Arial", 10),
                          bg=self.colors['primary'],
                          fg=self.colors['light'])
            sub.pack()

    # -----------
    # Welcome Screen
    # -----------
    def show_welcome(self):
        self.clear()
        
        # Header
        self.create_header("🏨 Grand Hotel Booking System", "Your Comfort, Our Priority")
        
        # Main content
        content = tk.Frame(self.main_frame, bg=self.colors['light'])
        content.pack(expand=True, fill='both', padx=40, pady=20)
        
        # Welcome message
        welcome = tk.Label(content, 
                          text="Welcome to our premium hotel booking platform",
                          font=("Arial", 14),
                          bg=self.colors['light'],
                          fg=self.colors['dark'])
        welcome.pack(pady=(20, 30))
        
        # Button container
        btn_container = tk.Frame(content, bg=self.colors['light'])
        btn_container.pack(pady=20)
        
        # User section
        user_frame = tk.LabelFrame(btn_container, text="Customer Portal",
                                   font=("Arial", 12, "bold"),
                                   bg='white', padx=20, pady=20)
        user_frame.grid(row=0, column=0, padx=15, pady=10, sticky='nsew')
        
        ttk.Button(user_frame, text="🔑 Login", 
                  command=self.show_login,
                  style='Primary.TButton',
                  width=20).pack(pady=8)
        ttk.Button(user_frame, text="📝 Register", 
                  command=self.show_register,
                  style='Primary.TButton',
                  width=20).pack(pady=8)
        ttk.Button(user_frame, text="👁 Browse Rooms", 
                  command=self.show_browse_guest,
                  width=20).pack(pady=8)
        
        # Admin section
        admin_frame = tk.LabelFrame(btn_container, text="Admin Portal",
                                    font=("Arial", 12, "bold"),
                                    bg='white', padx=20, pady=20)
        admin_frame.grid(row=0, column=1, padx=15, pady=10, sticky='nsew')
        
        ttk.Button(admin_frame, text="🔐 Admin Login", 
                  command=self.show_admin_login,
                  style='Primary.TButton',
                  width=20).pack(pady=8)
        
        tk.Label(admin_frame, text="Default Credentials:",
                font=("Arial", 9),
                bg='white',
                fg='gray').pack(pady=(15, 2))
        tk.Label(admin_frame, text="Email: admin@hotel",
                font=("Arial", 8),
                bg='white',
                fg='gray').pack()
        tk.Label(admin_frame, text="Password: admin123",
                font=("Arial", 8),
                bg='white',
                fg='gray').pack()
        
        # Footer
        footer = tk.Label(self.main_frame,
                         text="© 2024 Grand Hotel - All Rights Reserved",
                         font=("Arial", 9),
                         bg=self.colors['light'],
                         fg='gray')
        footer.pack(side='bottom', pady=10)

    # -----------
    # User Registration
    # -----------
    def show_register(self):
        self.clear()
        self.create_header("Create Account", "Join us for exclusive benefits")
        
        # Form container
        form_container = tk.Frame(self.main_frame, bg='white')
        form_container.pack(pady=30, padx=200)
        form_container.configure(relief='raised', borderwidth=2)
        
        form = tk.Frame(form_container, bg='white', padx=40, pady=30)
        form.pack()
        
        # Form fields
        fields = [
            ("Full Name:", "name"),
            ("Email Address:", "email"),
            ("Phone Number:", "phone"),
            ("Password:", "password")
        ]
        
        entries = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label, font=("Arial", 10), bg='white').grid(row=i, column=0, sticky='w', pady=8)
            if key == "password":
                entries[key] = ttk.Entry(form, show="*", width=30, font=("Arial", 10))
            else:
                entries[key] = ttk.Entry(form, width=30, font=("Arial", 10))
            entries[key].grid(row=i, column=1, pady=8, padx=10)

        def do_register():
            name = entries['name'].get().strip()
            email = entries['email'].get().strip().lower()
            phone = entries['phone'].get().strip()
            pw = entries['password'].get()
            
            if not (name and email and pw):
                messagebox.showerror("Error", "Please fill all required fields")
                return
            
            if len(pw) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return
            
            conn = get_db()
            c = conn.cursor()
            try:
                c.execute("INSERT INTO Customers (name,email,phone,password_hash) VALUES (?,?,?,?)",
                          (name, email, phone, hash_password(pw)))
                conn.commit()
                messagebox.showinfo("Success", "Registration successful! Please login.")
                self.show_login()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Email already registered")
            finally:
                conn.close()

        # Buttons
        btn_frame = tk.Frame(form, bg='white')
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Register", command=do_register,
                  style='Success.TButton', width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_welcome,
                  width=15).pack(side='left', padx=5)

    # -----------
    # User Login
    # -----------
    def show_login(self):
        self.clear()
        self.create_header("Customer Login", "Access your bookings")
        
        form_container = tk.Frame(self.main_frame, bg='white')
        form_container.pack(pady=40, padx=250)
        form_container.configure(relief='raised', borderwidth=2)
        
        form = tk.Frame(form_container, bg='white', padx=40, pady=30)
        form.pack()
        
        tk.Label(form, text="Email Address:", font=("Arial", 10), bg='white').grid(row=0, column=0, sticky='w', pady=10)
        email_e = ttk.Entry(form, width=30, font=("Arial", 10))
        email_e.grid(row=0, column=1, pady=10, padx=10)
        
        tk.Label(form, text="Password:", font=("Arial", 10), bg='white').grid(row=1, column=0, sticky='w', pady=10)
        pw_e = ttk.Entry(form, show="*", width=30, font=("Arial", 10))
        pw_e.grid(row=1, column=1, pady=10, padx=10)

        def do_login():
            email = email_e.get().strip().lower()
            pw = pw_e.get()
            
            if not (email and pw):
                messagebox.showerror("Error", "Please enter email and password")
                return
            
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM Customers WHERE email = ?", (email,))
            row = c.fetchone()
            conn.close()
            
            if row and verify_password(pw, row["password_hash"]):
                self.user = row
                messagebox.showinfo("Success", f"Welcome back, {row['name']}!")
                self.show_user_dashboard()
            else:
                messagebox.showerror("Error", "Invalid email or password")

        btn_frame = tk.Frame(form, bg='white')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Login", command=do_login,
                  style='Success.TButton', width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_welcome,
                  width=15).pack(side='left', padx=5)

    # -----------
    # Admin Login
    # -----------
    def show_admin_login(self):
        self.clear()
        self.create_header("Admin Login", "Management Portal Access")
        
        form_container = tk.Frame(self.main_frame, bg='white')
        form_container.pack(pady=40, padx=250)
        form_container.configure(relief='raised', borderwidth=2)
        
        form = tk.Frame(form_container, bg='white', padx=40, pady=30)
        form.pack()
        
        tk.Label(form, text="Email:", font=("Arial", 10), bg='white').grid(row=0, column=0, sticky='w', pady=10)
        email_e = ttk.Entry(form, width=30, font=("Arial", 10))
        email_e.grid(row=0, column=1, pady=10, padx=10)
        
        tk.Label(form, text="Password:", font=("Arial", 10), bg='white').grid(row=1, column=0, sticky='w', pady=10)
        pw_e = ttk.Entry(form, show="*", width=30, font=("Arial", 10))
        pw_e.grid(row=1, column=1, pady=10, padx=10)

        def do_login():
            email = email_e.get().strip().lower()
            pw = pw_e.get()
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM Staff WHERE email = ?", (email,))
            row = c.fetchone()
            conn.close()
            
            if row and verify_password(pw, row["password_hash"]):
                self.staff = row
                messagebox.showinfo("Success", f"Welcome, {row['name']}!")
                self.show_admin_dashboard()
            else:
                messagebox.showerror("Error", "Invalid admin credentials")

        btn_frame = tk.Frame(form, bg='white')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Login", command=do_login,
                  style='Success.TButton', width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_welcome,
                  width=15).pack(side='left', padx=5)

    # -----------
    # Guest Browse Rooms
    # -----------
    def show_browse_guest(self):
        self.clear()
        self.create_header("Browse Available Rooms", "Find your perfect stay")
        
        # Search frame
        search_frame = tk.Frame(self.main_frame, bg='white', padx=20, pady=15)
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        tk.Label(search_frame, text="Check-in:", font=("Arial", 10), bg='white').grid(row=0, column=0, padx=5)
        ci = DateEntry(search_frame, width=15, date_pattern='dd-mm-yyyy', mindate=date.today())
        ci.grid(row=0, column=1, padx=5)
        
        tk.Label(search_frame, text="Check-out:", font=("Arial", 10), bg='white').grid(row=0, column=2, padx=5)
        co = DateEntry(search_frame, width=15, date_pattern='dd-mm-yyyy', mindate=date.today() + timedelta(days=1))
        co.grid(row=0, column=3, padx=5)
        
        tk.Label(search_frame, text="Room Type:", font=("Arial", 10), bg='white').grid(row=0, column=4, padx=5)
        room_type_var = tk.StringVar(value="All")
        room_type_combo = ttk.Combobox(search_frame, textvariable=room_type_var, 
                                       values=["All", "Single", "Double", "Suite"],
                                       state='readonly', width=12)
        room_type_combo.grid(row=0, column=5, padx=5)
        
        # Results frame
        results_frame = tk.Frame(self.main_frame, bg='white')
        results_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Treeview
        columns = ("num", "type", "price", "desc")
        tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=15)
        tree.heading("num", text="Room Number")
        tree.heading("type", text="Room Type")
        tree.heading("price", text="Price/Night (₹)")
        tree.heading("desc", text="Description")
        
        tree.column("num", width=100, anchor='center')
        tree.column("type", width=100, anchor='center')
        tree.column("price", width=120, anchor='center')
        tree.column("desc", width=400)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def search():
            start = ci.get_date()
            end = co.get_date()
            
            if end <= start:
                messagebox.showerror("Error", "Check-out must be after check-in date")
                return
            
            room_type = room_type_var.get()
            rooms = find_available_rooms(start, end, room_type)
            
            for i in tree.get_children():
                tree.delete(i)
            
            if not rooms:
                messagebox.showinfo("No Rooms", "No rooms available for selected dates and type")
                return
            
            for r in rooms:
                tree.insert("", "end", values=(
                    r["room_number"], 
                    r["room_type"], 
                    f"₹{r['price_per_night']:.2f}", 
                    r["description"]
                ))
            
            messagebox.showinfo("Search Results", f"Found {len(rooms)} available room(s)")

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="🔍 Search", command=search,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_welcome).pack(side='left', padx=5)

    # -----------
    # User Dashboard
    # -----------
    def show_user_dashboard(self):
        self.clear()
        self.create_header(f"Welcome, {self.user['name']}", "Manage your bookings")
        
        # Quick actions
        actions = tk.Frame(self.main_frame, bg=self.colors['light'])
        actions.pack(pady=20)
        
        ttk.Button(actions, text="🏨 Browse & Book Rooms", 
                  command=self.show_browse_and_book,
                  style='Primary.TButton',
                  width=25).pack(side='left', padx=10)
        ttk.Button(actions, text="📋 My Bookings", 
                  command=self.show_my_bookings,
                  style='Primary.TButton',
                  width=25).pack(side='left', padx=10)
        ttk.Button(actions, text="🚪 Logout", 
                  command=self.do_logout,
                  width=25).pack(side='left', padx=10)

    def do_logout(self):
        self.user = None
        self.staff = None
        messagebox.showinfo("Logged Out", "You have been logged out successfully")
        self.show_welcome()

    # -----------
    # Browse and Book
    # -----------
    def show_browse_and_book(self):
        self.clear()
        self.create_header("Book Your Room", "Find and reserve your perfect accommodation")
        
        # Search criteria
        search_frame = tk.Frame(self.main_frame, bg='white', padx=20, pady=15)
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        tk.Label(search_frame, text="Check-in:", font=("Arial", 10), bg='white').grid(row=0, column=0, padx=5)
        ci = DateEntry(search_frame, width=15, date_pattern='dd-mm-yyyy', mindate=date.today())
        ci.grid(row=0, column=1, padx=5)
        
        tk.Label(search_frame, text="Check-out:", font=("Arial", 10), bg='white').grid(row=0, column=2, padx=5)
        co = DateEntry(search_frame, width=15, date_pattern='dd-mm-yyyy', mindate=date.today() + timedelta(days=1))
        co.grid(row=0, column=3, padx=5)
        
        tk.Label(search_frame, text="Room Type:", font=("Arial", 10), bg='white').grid(row=0, column=4, padx=5)
        room_type_var = tk.StringVar(value="All")
        room_type_combo = ttk.Combobox(search_frame, textvariable=room_type_var,
                                       values=["All", "Single", "Double", "Suite"],
                                       state='readonly', width=12)
        room_type_combo.grid(row=0, column=5, padx=5)
        
        # Results
        results_frame = tk.Frame(self.main_frame, bg='white')
        results_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("id", "num", "type", "price", "desc")
        tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=12)
        tree.heading("id", text="ID")
        tree.heading("num", text="Room Number")
        tree.heading("type", text="Type")
        tree.heading("price", text="Price/Night (₹)")
        tree.heading("desc", text="Description")
        
        tree.column("id", width=50, anchor='center')
        tree.column("num", width=100, anchor='center')
        tree.column("type", width=100, anchor='center')
        tree.column("price", width=120, anchor='center')
        tree.column("desc", width=350)
        
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def search():
            start = ci.get_date()
            end = co.get_date()
            
            if end <= start:
                messagebox.showerror("Error", "Check-out must be after check-in date")
                return
            
            room_type = room_type_var.get()
            rooms = find_available_rooms(start, end, room_type)
            
            for i in tree.get_children():
                tree.delete(i)
            
            if not rooms:
                messagebox.showinfo("No Rooms", "No rooms available for selected dates and type")
                return
            
            for r in rooms:
                tree.insert("", "end", iid=str(r["room_id"]), values=(
                    r["room_id"],
                    r["room_number"], 
                    r["room_type"], 
                    f"₹{r['price_per_night']:.2f}", 
                    r["description"]
                ))
            
            tree._checkin = start
            tree._checkout = end
            messagebox.showinfo("Search Results", f"Found {len(rooms)} available room(s)")

        def book_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a room to book")
                return
            
            room_id = int(sel[0])
            start = tree._checkin
            end = tree._checkout
            
            if not check_availability(room_id, start, end):
                messagebox.showerror("Error", "Room no longer available. Please search again.")
                return
            
            # Create booking
            booking_id = create_booking(self.user["customer_id"], room_id, start, end)
            
            # Calculate total
            total_nights = (end - start).days
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT price_per_night, room_number FROM Rooms WHERE room_id = ?", (room_id,))
            r = c.fetchone()
            price = r["price_per_night"]
            room_num = r["room_number"]
            conn.close()
            
            total_amount = price * total_nights
            
            proceed = messagebox.askyesno("Confirm Booking", 
                f"Room: {room_num}\n"
                f"Check-in: {format_date(start)}\n"
                f"Check-out: {format_date(end)}\n"
                f"Nights: {total_nights}\n"
                f"Total: ₹{total_amount:.2f}\n\n"
                f"Proceed to payment?")
            
            if proceed:
                self.show_payment(booking_id, total_amount)
            else:
                messagebox.showinfo("Booking Created", 
                    "Booking created with Pending status.\n"
                    "You can complete payment from 'My Bookings'.")
                self.show_my_bookings()

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="🔍 Search", command=search,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="✅ Book Selected", command=book_selected,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_user_dashboard).pack(side='left', padx=5)

    # -----------
    # Payment Window
    # -----------
    def show_payment(self, booking_id, amount):
        pay_win = tk.Toplevel(self)
        pay_win.title("Complete Payment")
        pay_win.geometry("400x350")
        pay_win.configure(bg='white')
        pay_win.transient(self)
        pay_win.grab_set()
        
        # Header
        header = tk.Frame(pay_win, bg=self.colors['secondary'], height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="💳 Payment", 
                font=("Arial", 18, "bold"),
                bg=self.colors['secondary'],
                fg='white').pack(pady=15)
        
        # Content
        content = tk.Frame(pay_win, bg='white', padx=30, pady=20)
        content.pack(fill='both', expand=True)
        
        tk.Label(content, text=f"Total Amount: ₹{amount:.2f}", 
                font=("Arial", 16, "bold"),
                bg='white',
                fg=self.colors['success']).pack(pady=15)
        
        tk.Label(content, text="Select Payment Method:", 
                font=("Arial", 11),
                bg='white').pack(pady=10)
        
        var = tk.StringVar()
        
        payment_methods = [
            ("💳 Credit/Debit Card", "Card"),
            ("📱 UPI Payment", "UPI"),
            ("💵 Cash on Arrival", "Cash"),
            ("🏦 Net Banking", "NetBanking")
        ]
        
        for text, value in payment_methods:
            rb = tk.Radiobutton(content, text=text, variable=var, value=value,
                               font=("Arial", 10), bg='white',
                               selectcolor=self.colors['light'])
            rb.pack(anchor='w', padx=20, pady=5)

        def do_pay():
            mode = var.get()
            if not mode:
                messagebox.showerror("Error", "Please select a payment method")
                return
            
            record_payment(booking_id, amount, mode)
            messagebox.showinfo("Success", 
                "Payment successful! ✅\n"
                "Your booking is confirmed.\n"
                "Thank you for choosing our hotel!")
            pay_win.destroy()
            self.show_my_bookings()

        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Pay Now", command=do_pay,
                  style='Success.TButton', width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=pay_win.destroy,
                  width=15).pack(side='left', padx=5)

    # -----------
    # My Bookings
    # -----------
    def show_my_bookings(self):
        self.clear()
        self.create_header("My Bookings", "View and manage your reservations")
        
        # Bookings list
        list_frame = tk.Frame(self.main_frame, bg='white')
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("id", "room", "in", "out", "status", "paid")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        tree.heading("id", text="Booking ID")
        tree.heading("room", text="Room")
        tree.heading("in", text="Check-in")
        tree.heading("out", text="Check-out")
        tree.heading("status", text="Status")
        tree.heading("paid", text="Payment")
        
        tree.column("id", width=80, anchor='center')
        tree.column("room", width=80, anchor='center')
        tree.column("in", width=120, anchor='center')
        tree.column("out", width=120, anchor='center')
        tree.column("status", width=100, anchor='center')
        tree.column("paid", width=100, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load():
            for i in tree.get_children():
                tree.delete(i)
            
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                SELECT b.booking_id, r.room_number, b.check_in, b.check_out, b.status,
                       CASE WHEN p.payment_id IS NOT NULL THEN 'Paid' ELSE 'Pending' END as payment_status
                FROM Bookings b 
                JOIN Rooms r ON b.room_id = r.room_id
                LEFT JOIN Payments p ON b.booking_id = p.booking_id
                WHERE b.customer_id = ?
                ORDER BY b.created_at DESC
            """, (self.user["customer_id"],))
            
            for r in c.fetchall():
                tree.insert("", "end", values=(
                    r["booking_id"], 
                    r["room_number"], 
                    format_date(r["check_in"]), 
                    format_date(r["check_out"]), 
                    r["status"],
                    r["payment_status"]
                ))
            conn.close()

        def pay_pending():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a booking")
                return
            
            values = tree.item(sel[0])["values"]
            bid = values[0]
            status = values[4]
            payment_status = values[5]
            
            if payment_status == "Paid":
                messagebox.showinfo("Info", "This booking is already paid")
                return
            
            if status == "Cancelled":
                messagebox.showinfo("Info", "Cannot pay for cancelled booking")
                return
            
            # Calculate amount
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                SELECT b.check_in, b.check_out, r.price_per_night 
                FROM Bookings b 
                JOIN Rooms r ON b.room_id = r.room_id 
                WHERE b.booking_id = ?
            """, (bid,))
            rr = c.fetchone()
            conn.close()
            
            start = datetime.strptime(rr["check_in"], "%Y-%m-%d").date()
            end = datetime.strptime(rr["check_out"], "%Y-%m-%d").date()
            total = (end - start).days * rr["price_per_night"]
            
            self.show_payment(bid, total)

        def cancel_booking():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a booking")
                return
            
            values = tree.item(sel[0])["values"]
            bid = values[0]
            status = values[4]
            
            if status == "Cancelled":
                messagebox.showinfo("Info", "Booking is already cancelled")
                return
            
            confirm = messagebox.askyesno("Cancel Booking", 
                "Are you sure you want to cancel this booking?\n"
                "Note: Refunds are processed within 5-7 business days.")
            
            if confirm:
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE Bookings SET status = 'Cancelled' WHERE booking_id = ?", (bid,))
                conn.commit()
                conn.close()
                messagebox.showinfo("Cancelled", "Booking cancelled successfully")
                load()

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="💳 Pay Selected", command=pay_pending,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Cancel Booking", command=cancel_booking,
                  style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_user_dashboard).pack(side='left', padx=5)
        
        load()

    # -----------
    # Admin Dashboard
    # -----------
    def show_admin_dashboard(self):
        self.clear()
        self.create_header("Admin Dashboard", "Hotel Management System")
        
        # Statistics cards
        stats = get_dashboard_stats()
        
        stats_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        stats_frame.pack(fill='x', padx=20, pady=20)
        
        stat_cards = [
            ("Total Rooms", stats['total_rooms'], self.colors['secondary']),
            ("Available", stats['available_rooms'], self.colors['success']),
            ("Total Bookings", stats['total_bookings'], self.colors['warning']),
            ("Confirmed", stats['confirmed_bookings'], self.colors['success']),
            ("Pending", stats['pending_bookings'], self.colors['danger']),
            ("Revenue", f"₹{stats['total_revenue']:.0f}", self.colors['primary'])
        ]
        
        for i, (label, value, color) in enumerate(stat_cards):
            card = tk.Frame(stats_frame, bg=color, relief='raised', borderwidth=2)
            card.grid(row=i//3, column=i%3, padx=10, pady=10, sticky='nsew')
            
            tk.Label(card, text=str(value), 
                    font=("Arial", 24, "bold"),
                    bg=color, fg='white').pack(pady=(15, 5))
            tk.Label(card, text=label, 
                    font=("Arial", 10),
                    bg=color, fg='white').pack(pady=(0, 15))
            
            stats_frame.grid_columnconfigure(i%3, weight=1)
        
        # Action buttons
        actions = tk.Frame(self.main_frame, bg=self.colors['light'])
        actions.pack(pady=20)
        
        ttk.Button(actions, text="🏨 Manage Rooms", 
                  command=self.show_manage_rooms,
                  style='Primary.TButton',
                  width=20).pack(side='left', padx=10)
        ttk.Button(actions, text="📋 View Bookings", 
                  command=self.show_view_bookings,
                  style='Primary.TButton',
                  width=20).pack(side='left', padx=10)
        ttk.Button(actions, text="💰 View Payments", 
                  command=self.show_view_payments,
                  style='Primary.TButton',
                  width=20).pack(side='left', padx=10)
        ttk.Button(actions, text="🚪 Logout", 
                  command=self.do_logout,
                  width=20).pack(side='left', padx=10)

    # -----------
    # Manage Rooms
    # -----------
    def show_manage_rooms(self):
        self.clear()
        self.create_header("Manage Rooms", "Add, edit, or remove rooms")
        
        list_frame = tk.Frame(self.main_frame, bg='white')
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("id", "num", "type", "price", "status", "desc")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=14)
        
        tree.heading("id", text="ID")
        tree.heading("num", text="Room No")
        tree.heading("type", text="Type")
        tree.heading("price", text="Price")
        tree.heading("status", text="Status")
        tree.heading("desc", text="Description")
        
        tree.column("id", width=50, anchor='center')
        tree.column("num", width=80, anchor='center')
        tree.column("type", width=80, anchor='center')
        tree.column("price", width=100, anchor='center')
        tree.column("status", width=100, anchor='center')
        tree.column("desc", width=300)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_rooms():
            for i in tree.get_children():
                tree.delete(i)
            
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM Rooms ORDER BY room_number")
            for r in c.fetchall():
                tree.insert("", "end", iid=str(r["room_id"]), values=(
                    r["room_id"], 
                    r["room_number"], 
                    r["room_type"], 
                    f"₹{r['price_per_night']:.2f}", 
                    r["status"], 
                    r["description"]
                ))
            conn.close()

        def add_room():
            add_win = tk.Toplevel(self)
            add_win.title("Add New Room")
            add_win.geometry("400x400")
            add_win.configure(bg='white')
            add_win.transient(self)
            add_win.grab_set()
            
            form = tk.Frame(add_win, bg='white', padx=30, pady=20)
            form.pack(fill='both', expand=True)
            
            tk.Label(form, text="Add New Room", 
                    font=("Arial", 16, "bold"),
                    bg='white').pack(pady=(0, 20))
            
            fields = {}
            
            tk.Label(form, text="Room Number:", bg='white').pack(anchor='w')
            fields['num'] = ttk.Entry(form, width=30)
            fields['num'].pack(pady=(0, 10))
            
            tk.Label(form, text="Room Type:", bg='white').pack(anchor='w')
            fields['type'] = ttk.Combobox(form, values=["Single", "Double", "Suite"], 
                                         state='readonly', width=28)
            fields['type'].pack(pady=(0, 10))
            
            tk.Label(form, text="Price per Night:", bg='white').pack(anchor='w')
            fields['price'] = ttk.Entry(form, width=30)
            fields['price'].pack(pady=(0, 10))
            
            tk.Label(form, text="Description:", bg='white').pack(anchor='w')
            fields['desc'] = tk.Text(form, width=30, height=4)
            fields['desc'].pack(pady=(0, 10))
            
            def save():
                num = fields['num'].get().strip()
                rtype = fields['type'].get()
                price_str = fields['price'].get().strip()
                desc = fields['desc'].get("1.0", "end").strip()
                
                if not (num and rtype and price_str):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                try:
                    price = float(price_str)
                    if price <= 0:
                        raise ValueError()
                except ValueError:
                    messagebox.showerror("Error", "Invalid price")
                    return
                
                conn = get_db()
                c = conn.cursor()
                try:
                    c.execute("""
                        INSERT INTO Rooms (room_number, room_type, price_per_night, description) 
                        VALUES (?,?,?,?)
                    """, (num, rtype, price, desc))
                    conn.commit()
                    messagebox.showinfo("Success", "Room added successfully")
                    add_win.destroy()
                    load_rooms()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Room number already exists")
                finally:
                    conn.close()
            
            btn_frame = tk.Frame(form, bg='white')
            btn_frame.pack(pady=10)
            
            ttk.Button(btn_frame, text="Save", command=save,
                      style='Success.TButton', width=12).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel", command=add_win.destroy,
                      width=12).pack(side='left', padx=5)

        def edit_room():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a room")
                return
            
            rid = int(sel[0])
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM Rooms WHERE room_id = ?", (rid,))
            r = c.fetchone()
            conn.close()
            
            edit_win = tk.Toplevel(self)
            edit_win.title("Edit Room")
            edit_win.geometry("400x450")
            edit_win.configure(bg='white')
            edit_win.transient(self)
            edit_win.grab_set()
            
            form = tk.Frame(edit_win, bg='white', padx=30, pady=20)
            form.pack(fill='both', expand=True)
            
            tk.Label(form, text="Edit Room", 
                    font=("Arial", 16, "bold"),
                    bg='white').pack(pady=(0, 20))
            
            fields = {}
            
            tk.Label(form, text="Room Number:", bg='white').pack(anchor='w')
            fields['num'] = ttk.Entry(form, width=30)
            fields['num'].insert(0, r["room_number"])
            fields['num'].pack(pady=(0, 10))
            
            tk.Label(form, text="Room Type:", bg='white').pack(anchor='w')
            fields['type'] = ttk.Combobox(form, values=["Single", "Double", "Suite"], 
                                         state='readonly', width=28)
            fields['type'].set(r["room_type"])
            fields['type'].pack(pady=(0, 10))
            
            tk.Label(form, text="Price per Night:", bg='white').pack(anchor='w')
            fields['price'] = ttk.Entry(form, width=30)
            fields['price'].insert(0, r["price_per_night"])
            fields['price'].pack(pady=(0, 10))
            
            tk.Label(form, text="Status:", bg='white').pack(anchor='w')
            fields['status'] = ttk.Combobox(form, 
                                           values=["Available", "Booked", "Maintenance"], 
                                           state='readonly', width=28)
            fields['status'].set(r["status"])
            fields['status'].pack(pady=(0, 10))
            
            tk.Label(form, text="Description:", bg='white').pack(anchor='w')
            fields['desc'] = tk.Text(form, width=30, height=4)
            fields['desc'].insert("1.0", r["description"])
            fields['desc'].pack(pady=(0, 10))
            
            def save():
                num = fields['num'].get().strip()
                rtype = fields['type'].get()
                price_str = fields['price'].get().strip()
                status = fields['status'].get()
                desc = fields['desc'].get("1.0", "end").strip()
                
                if not (num and rtype and price_str and status):
                    messagebox.showerror("Error", "All fields are required")
                    return
                
                try:
                    price = float(price_str)
                    if price <= 0:
                        raise ValueError()
                except ValueError:
                    messagebox.showerror("Error", "Invalid price")
                    return
                
                conn = get_db()
                c = conn.cursor()
                try:
                    c.execute("""
                        UPDATE Rooms 
                        SET room_number=?, room_type=?, price_per_night=?, status=?, description=? 
                        WHERE room_id=?
                    """, (num, rtype, price, status, desc, rid))
                    conn.commit()
                    messagebox.showinfo("Success", "Room updated successfully")
                    edit_win.destroy()
                    load_rooms()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Room number conflict")
                finally:
                    conn.close()
            
            btn_frame = tk.Frame(form, bg='white')
            btn_frame.pack(pady=10)
            
            ttk.Button(btn_frame, text="Update", command=save,
                      style='Success.TButton', width=12).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel", command=edit_win.destroy,
                      width=12).pack(side='left', padx=5)

        def delete_room():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a room")
                return
            
            rid = int(sel[0])
            
            confirm = messagebox.askyesno("Delete Room", 
                "Are you sure you want to delete this room?\n"
                "This action cannot be undone.")
            
            if not confirm:
                return
            
            conn = get_db()
            c = conn.cursor()
            
            # Check if room has any bookings
            c.execute("SELECT COUNT(*) as cnt FROM Bookings WHERE room_id = ?", (rid,))
            if c.fetchone()['cnt'] > 0:
                messagebox.showerror("Error", 
                    "Cannot delete room with existing bookings.\n"
                    "Please cancel all bookings first.")
                conn.close()
                return
            
            c.execute("DELETE FROM Rooms WHERE room_id = ?", (rid,))
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Room deleted successfully")
            load_rooms()

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="➕ Add Room", command=add_room,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="✏️ Edit Selected", command=edit_room,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🗑️ Delete Selected", command=delete_room,
                  style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_admin_dashboard).pack(side='left', padx=5)
        
        load_rooms()

    # -----------
    # View Bookings
    # -----------
    def show_view_bookings(self):
        self.clear()
        self.create_header("All Bookings", "View and manage all reservations")
        
        list_frame = tk.Frame(self.main_frame, bg='white')
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("id", "customer", "room", "in", "out", "status")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=16)
        
        tree.heading("id", text="ID")
        tree.heading("customer", text="Customer")
        tree.heading("room", text="Room")
        tree.heading("in", text="Check-in")
        tree.heading("out", text="Check-out")
        tree.heading("status", text="Status")
        
        tree.column("id", width=60, anchor='center')
        tree.column("customer", width=150)
        tree.column("room", width=80, anchor='center')
        tree.column("in", width=120, anchor='center')
        tree.column("out", width=120, anchor='center')
        tree.column("status", width=100, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load():
            for i in tree.get_children():
                tree.delete(i)
            
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                SELECT b.booking_id, cust.name as customer, r.room_number as room, 
                       b.check_in, b.check_out, b.status
                FROM Bookings b
                LEFT JOIN Customers cust ON b.customer_id = cust.customer_id
                LEFT JOIN Rooms r ON b.room_id = r.room_id
                ORDER BY b.created_at DESC
            """)
            for r in c.fetchall():
                tree.insert("", "end", values=(
                    r["booking_id"], 
                    r["customer"], 
                    r["room"], 
                    format_date(r["check_in"]), 
                    format_date(r["check_out"]), 
                    r["status"]
                ))
            conn.close()

        def set_status():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("Error", "Please select a booking")
                return
            
            bid = tree.item(sel[0])["values"][0]
            
            status_win = tk.Toplevel(self)
            status_win.title("Update Status")
            status_win.geometry("300x200")
            status_win.configure(bg='white')
            status_win.transient(self)
            status_win.grab_set()
            
            tk.Label(status_win, text="Select New Status", 
                    font=("Arial", 12, "bold"),
                    bg='white').pack(pady=20)
            
            status_var = tk.StringVar()
            
            statuses = ["Pending", "Confirmed", "Completed", "Cancelled"]
            for s in statuses:
                tk.Radiobutton(status_win, text=s, variable=status_var, value=s,
                              font=("Arial", 10), bg='white').pack(anchor='w', padx=40, pady=5)
            
            def update():
                new_status = status_var.get()
                if not new_status:
                    messagebox.showerror("Error", "Please select a status")
                    return
                
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE Bookings SET status = ? WHERE booking_id = ?", (new_status, bid))
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Status updated successfully")
                status_win.destroy()
                load()
            
            ttk.Button(status_win, text="Update", command=update,
                      style='Success.TButton', width=15).pack(pady=10)

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="📝 Set Status", command=set_status,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🔄 Refresh", command=load,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_admin_dashboard).pack(side='left', padx=5)
        
        load()

    # -----------
    # View Payments
    # -----------
    def show_view_payments(self):
        self.clear()
        self.create_header("Payment History", "View all payment transactions")
        
        list_frame = tk.Frame(self.main_frame, bg='white')
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        columns = ("id", "booking", "customer", "amount", "date", "mode")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=16)
        
        tree.heading("id", text="Payment ID")
        tree.heading("booking", text="Booking ID")
        tree.heading("customer", text="Customer")
        tree.heading("amount", text="Amount")
        tree.heading("date", text="Payment Date")
        tree.heading("mode", text="Mode")
        
        tree.column("id", width=80, anchor='center')
        tree.column("booking", width=80, anchor='center')
        tree.column("customer", width=150)
        tree.column("amount", width=120, anchor='center')
        tree.column("date", width=180, anchor='center')
        tree.column("mode", width=100, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load():
            for i in tree.get_children():
                tree.delete(i)
            
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                SELECT p.payment_id, p.booking_id, c.name as customer, 
                       p.amount, p.payment_date, p.payment_mode
                FROM Payments p
                LEFT JOIN Bookings b ON p.booking_id = b.booking_id
                LEFT JOIN Customers c ON b.customer_id = c.customer_id
                ORDER BY p.payment_date DESC
            """)
            
            total_revenue = 0
            for r in c.fetchall():
                tree.insert("", "end", values=(
                    r["payment_id"], 
                    r["booking_id"], 
                    r["customer"] or "N/A",
                    f"₹{r['amount']:.2f}", 
                    r["payment_date"], 
                    r["payment_mode"]
                ))
                total_revenue += r["amount"]
            
            conn.close()
            
            # Show total revenue
            total_label.config(text=f"Total Revenue: ₹{total_revenue:.2f}")

        # Total revenue display
        total_frame = tk.Frame(self.main_frame, bg=self.colors['success'], pady=10)
        total_frame.pack(fill='x', padx=20, pady=(0, 10))
        
        total_label = tk.Label(total_frame, text="Total Revenue: ₹0.00",
                              font=("Arial", 14, "bold"),
                              bg=self.colors['success'],
                              fg='white')
        total_label.pack()

        btn_frame = tk.Frame(self.main_frame, bg=self.colors['light'])
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="🔄 Refresh", command=load,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Back", command=self.show_admin_dashboard).pack(side='left', padx=5)
        
        load()


# ---------------------------
# Entry point
# ---------------------------
if __name__ == "__main__":
    try:
        # Check if tkcalendar is installed
        import tkcalendar
    except ImportError:
        print("Error: tkcalendar module not found!")
        print("Please install it using: pip install tkcalendar")
        import sys
        sys.exit(1)
    
    create_tables()
    seed_data()
    app = HotelApp()
    app.mainloop()
