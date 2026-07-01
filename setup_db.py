"""
setup_db.py
===========
Chạy file này một lần để tạo mock database SQLite dùng cho Capstone Ngày 7.
Kết quả: file acb_mock.db trong cùng thư mục.

Usage:
    python setup_db.py
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "acb_mock.db"
random.seed(42)

def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ── Schema ───────────────────────────────────────────────────────
cur.executescript("""
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS loan_products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   TEXT PRIMARY KEY,
    full_name     TEXT NOT NULL,
    customer_type TEXT NOT NULL CHECK(customer_type IN ('individual','corporate')),
    segment       TEXT CHECK(segment IN ('mass','premium','private')),
    city          TEXT,
    created_at    TIMESTAMP NOT NULL
);

CREATE TABLE accounts (
    account_id   TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL REFERENCES customers(customer_id),
    account_type TEXT NOT NULL CHECK(account_type IN ('checking','savings','loan')),
    balance      DECIMAL(18,2) NOT NULL DEFAULT 0,
    currency     TEXT NOT NULL DEFAULT 'VND',
    status       TEXT NOT NULL CHECK(status IN ('active','frozen','closed')),
    opened_at    TIMESTAMP NOT NULL
);

CREATE TABLE transactions (
    transaction_id   TEXT PRIMARY KEY,
    account_id       TEXT NOT NULL REFERENCES accounts(account_id),
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('deposit','withdrawal','transfer_in','transfer_out','fee')),
    amount           DECIMAL(18,2) NOT NULL,
    direction        TEXT NOT NULL CHECK(direction IN ('credit','debit')),
    description      TEXT,
    channel          TEXT CHECK(channel IN ('mobile','internet','atm','branch','pos')),
    status           TEXT NOT NULL CHECK(status IN ('completed','pending','failed','reversed')),
    transacted_at    TIMESTAMP NOT NULL
);

CREATE TABLE loan_products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    loan_type       TEXT NOT NULL CHECK(loan_type IN ('personal','mortgage','business','auto')),
    interest_rate   DECIMAL(5,2) NOT NULL,
    max_term_months INTEGER NOT NULL,
    min_amount      DECIMAL(18,2) NOT NULL,
    max_amount      DECIMAL(18,2) NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE loans (
    loan_id         TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
    product_id      TEXT NOT NULL REFERENCES loan_products(product_id),
    principal       DECIMAL(18,2) NOT NULL,
    outstanding     DECIMAL(18,2) NOT NULL,
    term_months     INTEGER NOT NULL,
    monthly_payment DECIMAL(18,2) NOT NULL,
    loan_status     TEXT NOT NULL CHECK(loan_status IN ('active','closed','overdue','written_off')),
    disbursed_at    TIMESTAMP NOT NULL,
    maturity_at     TIMESTAMP NOT NULL
);
""")

# ── Customers (30 rows) ──────────────────────────────────────────
individuals = [
    ("Nguyễn Văn An", "Hà Nội"),
    ("Trần Thị Bích", "Hồ Chí Minh"),
    ("Lê Quang Minh", "Đà Nẵng"),
    ("Phạm Thu Hương", "Hồ Chí Minh"),
    ("Hoàng Đức Thắng", "Hà Nội"),
    ("Nguyễn Thị Lan", "Cần Thơ"),
    ("Vũ Minh Tuấn", "Hải Phòng"),
    ("Đỗ Thị Mai", "Hồ Chí Minh"),
    ("Bùi Văn Hùng", "Hà Nội"),
    ("Trịnh Thị Nga", "Đà Nẵng"),
    ("Đinh Công Sơn", "Hồ Chí Minh"),
    ("Cao Thị Linh", "Hà Nội"),
    ("Lý Văn Thành", "Hồ Chí Minh"),
    ("Mai Thị Hoa", "Huế"),
    ("Phan Quốc Bảo", "Hồ Chí Minh"),
    ("Tô Thị Yến", "Hà Nội"),
    ("Hà Văn Long", "Đà Nẵng"),
    ("Đặng Thị Thu", "Hồ Chí Minh"),
    ("Ngô Tuấn Anh", "Hà Nội"),
    ("Lưu Thị Phương", "Cần Thơ"),
]
corporates = [
    ("Công ty TNHH Thương Mại XYZ", "Hồ Chí Minh"),
    ("Công ty CP Sản Xuất ABC", "Hà Nội"),
    ("Tập đoàn Đầu Tư DEF", "Hồ Chí Minh"),
    ("Công ty TNHH Công Nghệ GHI", "Đà Nẵng"),
    ("Công ty CP Xuất Nhập Khẩu JKL", "Hồ Chí Minh"),
    ("Công ty TNHH Bất Động Sản MNO", "Hà Nội"),
    ("Công ty CP Logistics PQR", "Hải Phòng"),
    ("Tập đoàn Xây Dựng STU", "Hồ Chí Minh"),
    ("Công ty TNHH Dược Phẩm VWX", "Hà Nội"),
    ("Công ty CP Thực Phẩm YZA", "Hồ Chí Minh"),
]

segments = ["mass"] * 12 + ["premium"] * 6 + ["private"] * 2
customers = []
start_date = datetime(2018, 1, 1)
end_date   = datetime(2023, 12, 31)

for i, (name, city) in enumerate(individuals):
    cid = f"CUS_{i+1:06d}"
    seg = segments[i % len(segments)]
    customers.append((cid, name, "individual", seg, city, fmt(random_date(start_date, end_date))))

for i, (name, city) in enumerate(corporates):
    cid = f"CUS_{i+21:06d}"
    customers.append((cid, name, "corporate", "premium", city, fmt(random_date(start_date, end_date))))

cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

# ── Loan Products (6 rows) ───────────────────────────────────────
products = [
    ("PROD_001", "Vay Tiêu Dùng Thông Thường", "personal",  12.5,  60,   5_000_000,    500_000_000, 1),
    ("PROD_002", "Vay Mua Nhà Ở",              "mortgage",   8.2, 300,  500_000_000, 10_000_000_000, 1),
    ("PROD_003", "Vay Kinh Doanh SME",         "business",  10.8, 120, 100_000_000,  5_000_000_000, 1),
    ("PROD_004", "Vay Mua Ô Tô",               "auto",       9.5,  84, 100_000_000,  2_000_000_000, 1),
    ("PROD_005", "Vay Du Học",                 "personal",  11.0,  84,  50_000_000,    500_000_000, 1),
    ("PROD_006", "Vay Sản Xuất Nông Nghiệp",   "business",   7.5,  60,  10_000_000,    500_000_000, 0),
]
cur.executemany("INSERT INTO loan_products VALUES (?,?,?,?,?,?,?,?)", products)

# ── Accounts ─────────────────────────────────────────────────────
accounts = []
acc_map  = {}   # customer_id → list of account_ids (checking/savings)
cust_ids = [r[0] for r in customers]

for i, cid in enumerate(cust_ids):
    # checking account
    aid_c = f"ACC_{i*2+1:010d}"
    balance_c = round(random.uniform(100_000, 200_000_000), 2)
    opened = fmt(random_date(datetime(2018,1,1), datetime(2023,12,31)))
    accounts.append((aid_c, cid, "checking", balance_c, "VND", "active", opened))

    # savings account (not everyone)
    if random.random() > 0.3:
        aid_s = f"ACC_{i*2+2:010d}"
        balance_s = round(random.uniform(0, 500_000_000), 2)
        accounts.append((aid_s, cid, "savings", balance_s, "VND", "active", opened))
        acc_map.setdefault(cid, []).extend([aid_c, aid_s])
    else:
        acc_map.setdefault(cid, []).append(aid_c)

# A few frozen/closed
accounts[5]  = (accounts[5][0],  accounts[5][1],  accounts[5][2],  accounts[5][3],  "VND", "frozen", accounts[5][6])
accounts[18] = (accounts[18][0], accounts[18][1], accounts[18][2], accounts[18][3], "VND", "closed", accounts[18][6])

cur.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?)", accounts)

all_account_ids = [a[0] for a in accounts if a[5] == "active"]

# ── Transactions (500 rows) ──────────────────────────────────────
channels    = ["mobile", "internet", "atm", "branch", "pos"]
chan_weights = [40, 30, 15, 10, 5]
statuses    = ["completed", "completed", "completed", "completed", "completed", "pending", "failed", "reversed"]

tx_types = {
    "deposit":       "credit",
    "withdrawal":    "debit",
    "transfer_in":   "credit",
    "transfer_out":  "debit",
    "fee":           "debit",
}

transactions = []
tx_start = datetime(2024, 1, 1)
tx_end   = datetime(2024, 12, 31)

for i in range(500):
    tid   = f"TXN_{i+1:08d}"
    aid   = random.choice(all_account_ids)
    ttype = random.choices(list(tx_types.keys()), weights=[25,20,20,20,15])[0]
    direc = tx_types[ttype]
    amt   = round(random.uniform(50_000, 50_000_000), 2)
    if ttype == "fee":
        amt = round(random.uniform(5_000, 200_000), 2)
    ch    = random.choices(channels, weights=chan_weights)[0]
    st    = random.choice(statuses)
    desc  = {
        "deposit":      "Nộp tiền mặt",
        "withdrawal":   "Rút tiền mặt",
        "transfer_in":  f"Nhận CK từ khách hàng {random.randint(1000,9999)}",
        "transfer_out": f"CK cho tài khoản {random.randint(100000,999999)}",
        "fee":          "Phí dịch vụ tháng",
    }[ttype]
    dt = fmt(random_date(tx_start, tx_end))
    transactions.append((tid, aid, ttype, amt, direc, desc, ch, st, dt))

cur.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)", transactions)

# ── Loans (25 rows) ──────────────────────────────────────────────
loan_cids = random.sample(cust_ids, 25)
loan_prods = ["PROD_001","PROD_002","PROD_003","PROD_004","PROD_005"]
loan_statuses = ["active","active","active","active","closed","overdue","written_off"]

loans = []
for i, cid in enumerate(loan_cids):
    lid   = f"LOAN_{i+1:06d}"
    pid   = random.choice(loan_prods)
    prod  = next(p for p in products if p[0]==pid)
    principal = round(random.uniform(float(prod[5]), min(float(prod[6]), float(prod[6])*0.3)), 2)
    rate  = prod[3] / 100 / 12
    term  = random.randint(12, prod[4])
    if rate > 0:
        monthly = round(principal * rate * (1+rate)**term / ((1+rate)**term - 1), 2)
    else:
        monthly = round(principal / term, 2)
    repaid   = round(principal * random.uniform(0, 0.8), 2)
    outstanding = round(max(0, principal - repaid), 2)
    lst   = random.choice(loan_statuses)
    dis   = random_date(datetime(2020,1,1), datetime(2023,6,30))
    mat   = dis + timedelta(days=30*term)
    loans.append((lid, cid, pid, principal, outstanding, term, monthly, lst, fmt(dis), fmt(mat)))

cur.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?,?)", loans)

conn.commit()

# ── Verify ───────────────────────────────────────────────────────
print("✅  Database created:", DB_PATH)
for tbl in ["customers","accounts","transactions","loan_products","loans"]:
    count = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"   {tbl}: {count} rows")

conn.close()
