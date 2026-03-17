import os
import socket
import select
import threading

SERVER_PORT = 5432
MAX_PENDING = 5
MAX_LINE = 4096

USERS_FILE = "users.txt"
STOCKS_FILE = "stocks.txt"

# Locks for protecting shared resources
file_lock = threading.Lock()
active_sessions_lock = threading.Lock()

# Active sessions: list of dicts {user_id, username, addr}
active_sessions = []

# Used to stop the accept loop during shutdown
shutdown_event = threading.Event()


def ensure_data_files():
    """Ensure user and stock data files exist and have reasonable defaults."""
    os.makedirs(os.path.dirname(os.path.abspath(USERS_FILE)), exist_ok=True)

    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w").close()

    if not os.path.exists(STOCKS_FILE):
        open(STOCKS_FILE, "w").close()

    # Ensure at least 4 users exist. IDs are 0..N-1.
    with file_lock:
        with open(USERS_FILE, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        if len(lines) < 4:
            defaults = [
                ("root@gmail.com", "Root", "User", "root", "Root01", 100.0),
                ("mary@gmail.com", "Mary", "User", "mary", "Mary01", 100.0),
                ("john@gmail.com", "John", "User", "john", "John01", 100.0),
                ("moe@gmail.com", "Moe", "User", "moe", "Moe01", 100.0),
            ]

            with open(USERS_FILE, "a") as f:
                for i in range(len(lines), 4):
                    email, first, last, username, password, balance = defaults[i]
                    f.write(f"{i},{email},{first},{last},{username},{password},{balance:.2f}\n")

    # Ensure stock file has at least one record
    with file_lock:
        with open(STOCKS_FILE, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        if not lines:
            with open(STOCKS_FILE, "a") as f:
                f.write("0,MSFT,Microsoft,100,0\n")


def read_users():
    """Return a list of user dicts from the users file."""
    with file_lock:
        with open(USERS_FILE, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

    users = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        users.append(
            {
                "id": int(parts[0]),
                "email": parts[1],
                "first": parts[2],
                "last": parts[3],
                "username": parts[4],
                "password": parts[5],
                "balance": float(parts[6]),
            }
        )
    return users


def write_users(users):
    with file_lock:
        with open(USERS_FILE, "w") as f:
            for u in users:
                f.write(
                    f"{u['id']},{u['email']},{u['first']},{u['last']},{u['username']},{u['password']},{u['balance']:.2f}\n"
                )


def read_stocks():
    """Return a list of stock dicts from the stocks file."""
    with file_lock:
        with open(STOCKS_FILE, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

    stocks = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        stocks.append(
            {
                "id": int(parts[0]),
                "symbol": parts[1],
                "name": parts[2],
                "amount": float(parts[3]),
                "owner_id": int(parts[4]),
            }
        )
    return stocks


def write_stocks(stocks):
    with file_lock:
        with open(STOCKS_FILE, "w") as f:
            for s in stocks:
                f.write(
                    f"{s['id']},{s['symbol']},{s['name']},{s['amount']},{s['owner_id']}\n"
                )


def add_active_session(user_id, username, addr):
    with active_sessions_lock:
        active_sessions.append({"id": user_id, "username": username, "addr": addr})


def remove_active_session(user_id, addr):
    with active_sessions_lock:
        active_sessions[:] = [s for s in active_sessions if not (s["id"] == user_id and s["addr"] == addr)]


def handle_client(conn, addr):
    """Handle a single client connection."""
    peer = f"{addr[0]}:{addr[1]}"
    print(f"Accepted connection from {peer}")

    logged_in = False
    current_user = None

    conn_file = conn.makefile("r")

    try:
        while not shutdown_event.is_set():
            line = conn_file.readline()
            if not line:
                break

            message = line.strip()
            if not message:
                continue

            parts = message.split()
            cmd = parts[0].upper()

            # LOGIN <UserID> <Password>
            if cmd == "LOGIN":
                if len(parts) != 3:
                    conn.sendall(b"400 invalid command\n")
                    continue

                user_id, password = parts[1], parts[2]
                users = read_users()
                match = next(
                    (u for u in users if u["username"].lower() == user_id.lower() and u["password"] == password),
                    None,
                )
                if not match:
                    conn.sendall(b"403 Wrong UserID or Password\n")
                    continue

                logged_in = True
                current_user = match
                add_active_session(current_user["id"], current_user["username"], addr[0])
                conn.sendall(b"200 OK\n")
                continue

            # QUIT can be performed without login
            if cmd == "QUIT":
                conn.sendall(b"200 OK\nClient quitting\n")
                break

            # All remaining commands require login
            if not logged_in:
                conn.sendall(b"403 Please login first\n")
                continue

            # LOGOUT
            if cmd == "LOGOUT":
                conn.sendall(b"200 OK\n")
                remove_active_session(current_user["id"], addr[0])
                break

            # WHO (root only)
            if cmd == "WHO":
                if current_user["username"].lower() != "root":
                    conn.sendall(b"403 Please login as root to use WHO\n")
                    continue

                with active_sessions_lock:
                    lines = [f"{s['username']} {s['addr']}" for s in active_sessions]

                response = "200 OK\nThe list of the active users:\n"
                response += "\n".join(lines) + "\n"
                conn.sendall(response.encode())
                continue

            # LIST
            if cmd == "LIST":
                stocks = read_stocks()
                users = read_users()
                user_map = {u["id"]: u["username"] for u in users}

                if current_user["username"].lower() == "root":
                    lines = [
                        f"{s['id']} {s['symbol']} {s['amount']} {user_map.get(s['owner_id'], 'unknown')}"
                        for s in stocks
                    ]
                    header = "200 OK\nThe list of records in the Stock database:\n"
                else:
                    lines = [
                        f"{s['id']} {s['symbol']} {s['amount']}"
                        for s in stocks
                        if s["owner_id"] == current_user["id"]
                    ]
                    header = f"200 OK\nThe list of records in the Stock database for {current_user['username']}:\n"

                if not lines:
                    lines = ["(none)"]

                conn.sendall((header + "\n".join(lines) + "\n").encode())
                continue

            # BALANCE
            if cmd == "BALANCE":
                balance = current_user["balance"]
                conn.sendall(f"200 OK\nBalance: ${balance:.2f}\n".encode())
                continue

            # DEPOSIT <amount>
            if cmd == "DEPOSIT" and len(parts) == 2:
                try:
                    amount = float(parts[1])
                except ValueError:
                    conn.sendall(b"400 invalid command\n")
                    continue
                if amount <= 0:
                    conn.sendall(b"400 invalid command\nDeposit amount must be positive\n")
                    continue

                users = read_users()
                for u in users:
                    if u["id"] == current_user["id"]:
                        u["balance"] += amount
                        current_user = u
                        break
                write_users(users)

                conn.sendall(
                    f"200 OK\nDeposit successful. New balance ${current_user['balance']:.2f}\n".encode()
                )
                continue

            # LOOKUP <ticker>
            if cmd == "LOOKUP" and len(parts) == 2:
                ticker = parts[1].upper()
                stocks = read_stocks()

                matches = []
                for s in stocks:
                    if s["owner_id"] == current_user["id"] and ticker in s["symbol"].upper():
                        matches.append(f"{s['symbol']} {s['amount']}")

                if matches:
                    plural = "s" if len(matches) != 1 else ""
                    response = f"200 OK\nFound {len(matches)} match{plural}\n"
                    response += "\n".join(matches) + "\n"
                else:
                    response = "404 Your search did not match any records.\n"

                conn.sendall(response.encode())
                continue

            # BUY <symbol> <amount> <price>
            if cmd == "BUY" and len(parts) == 4:
                symbol = parts[1]
                try:
                    amount = float(parts[2])
                    price = float(parts[3])
                except ValueError:
                    conn.sendall(b"400 invalid command\n")
                    continue

                if amount <= 0 or price <= 0:
                    conn.sendall(b"400 invalid command\n")
                    continue

                cost = amount * price
                users = read_users()
                for u in users:
                    if u["id"] == current_user["id"]:
                        if u["balance"] < cost:
                            conn.sendall(b"400 invalid command\nNot enough USD\n")
                            break
                        u["balance"] -= cost
                        current_user = u
                        break
                else:
                    conn.sendall(b"400 invalid command\nUser not found\n")
                    continue

                write_users(users)

                stocks = read_stocks()
                new_id = max((s["id"] for s in stocks), default=-1) + 1
                stocks.append(
                    {
                        "id": new_id,
                        "symbol": symbol,
                        "name": "N/A",
                        "amount": amount,
                        "owner_id": current_user["id"],
                    }
                )
                write_stocks(stocks)

                conn.sendall(b"200 OK\nStock purchased\n")
                continue

            # SELL <symbol> <price> <amount>
            if cmd == "SELL" and len(parts) == 4:
                symbol = parts[1]
                try:
                    price = float(parts[2])
                    amount = float(parts[3])
                except ValueError:
                    conn.sendall(b"400 invalid command\n")
                    continue

                if amount <= 0 or price <= 0:
                    conn.sendall(b"400 invalid command\n")
                    continue

                stocks = read_stocks()
                sold = False
                for s in stocks:
                    if s["owner_id"] == current_user["id"] and s["symbol"].upper() == symbol.upper():
                        if s["amount"] < amount:
                            break
                        s["amount"] -= amount
                        sold = True
                        break

                if not sold:
                    conn.sendall(b"400 invalid command\nNot enough stock\n")
                    continue

                write_stocks(stocks)

                users = read_users()
                for u in users:
                    if u["id"] == current_user["id"]:
                        u["balance"] += amount * price
                        current_user = u
                        break
                write_users(users)

                conn.sendall(b"200 OK\nStock sold\n")
                continue

            # SHUTDOWN
            if cmd == "SHUTDOWN":
                if current_user["username"].lower() != "root":
                    conn.sendall(b"403 Please login as root to shutdown\n")
                    continue

                conn.sendall(b"200 OK\nServer shutting down\n")
                shutdown_event.set()
                break

            conn.sendall(b"400 invalid command\n")

    finally:
        if logged_in and current_user is not None:
            remove_active_session(current_user["id"], addr[0])
        try:
            conn_file.close()
        except Exception:
            pass
        conn.close()
        print(f"Connection closed: {peer}")


def main():
    ensure_data_files()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", SERVER_PORT))
    server.listen(MAX_PENDING)

    print(f"Server listening on port {SERVER_PORT}...")

    # Limit concurrent client threads
    connection_semaphore = threading.Semaphore(10)

    try:
        while not shutdown_event.is_set():
            try:
                ready, _, _ = select.select([server], [], [], 1.0)
            except Exception:
                break

            if not ready:
                continue

            try:
                conn, addr = server.accept()
            except OSError:
                break

            # Limit maximum concurrent handlers
            if not connection_semaphore.acquire(blocking=False):
                conn.sendall(b"400 Server is busy. Try again later.\n")
                conn.close()
                continue

            def client_thread(c, a):
                try:
                    handle_client(c, a)
                finally:
                    connection_semaphore.release()

            thread = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
            thread.start()

            if shutdown_event.is_set():
                break

    finally:
        server.close()
        print("Server stopped.")


if __name__ == "__main__":
    main()
