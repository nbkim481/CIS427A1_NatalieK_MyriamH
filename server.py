import socket
import os
import threading

SERVER_PORT = 5432
MAX_PENDING = 5
MAX_LINE = 256

#define txt files
client = "users.txt"
stock = "stocks.txt"

# A lock to protect concurrent access to shared text files
file_lock = threading.Lock()

# Track active (logged-in) client sessions: (user_id, user_name, ip_address)
active_sessions = []
active_sessions_lock = threading.Lock()

# The listening socket, used for graceful shutdown.
server_socket = None

#create new user
def create_user(email, first_name, last_name, user_name, password, usd_balance):
    with open(client, "r") as f:
        lines = f.readlines()

    new_id = len(lines)

    with open(client, "a") as f:
        f.write(f"{new_id},{email},{first_name},{last_name},{user_name},{password},{usd_balance}\n")

    print("New user created")

#create new stock
def create_stock(stock_symbol, stock_name, stock_balance, user_id):
    with open(stock, "r") as f:
        lines = f.readlines()

    new_id = len(lines)

    with open(stock, "a") as f:
        f.write(f"{new_id},{stock_symbol},{stock_name},{stock_balance},{user_id}\n")


def handle_client(conn, addr):
    """Handle a single client connection."""
    print(f"Connected by {addr}")

    client_ip = addr[0]
    logged_in = False
    current_user_id = None
    current_user_name = None

    try:
        while True:
            data = conn.recv(MAX_LINE)
            if not data:
                break

            # receive message from client
            message = data.decode("utf-8").strip()
            print(message)

            parts = message.split()
            if not parts:
                conn.sendall(b"400 invalid command\n")
                continue

            cmd = parts[0].upper()

            # LOGIN <user_id> <password>
            if cmd == "LOGIN" and len(parts) == 3:
                user_id = parts[1]
                password = parts[2]

                with file_lock:
                    with open(client, "r") as f:
                        lines = f.readlines()

                for line in lines:
                    fields = [x.strip() for x in line.strip().split(",")]
                    if fields[0] == user_id and fields[5] == password:
                        logged_in = True
                        current_user_id = int(user_id)
                        current_user_name = fields[4]

                        with active_sessions_lock:
                            active_sessions.append((current_user_id, current_user_name, client_ip))

                        conn.sendall(b"200 OK\n")
                        break
                else:
                    conn.sendall(b"403 Wrong UserID or Password\n")
                continue

            # All other commands (except QUIT) require login
            if not logged_in and cmd != "QUIT":
                conn.sendall(b"403 Please login first\n")
                continue

            # WHO (root only)
            if cmd == "WHO" and len(parts) == 1:
                if current_user_id != 0:
                    conn.sendall(b"403 Please login as root to use WHO\n")
                    continue

                with active_sessions_lock:
                    users = [f"{name} {ip}" for (_, name, ip) in active_sessions]

                response = "200 OK\nThe list of the active users:\n"
                response += "\n".join(users) + "\n"
                conn.sendall(response.encode())
                continue

            # LOGOUT [name]
            if cmd == "LOGOUT" and len(parts) in (1, 2):
                conn.sendall(b"200 OK\n")

                # Remove this session immediately
                if logged_in and current_user_id is not None:
                    with active_sessions_lock:
                        active_sessions[:] = [s for s in active_sessions if not (s[0] == current_user_id and s[2] == client_ip)]

                break

            # BALANCE <user_id>
            if cmd == "BALANCE" and len(parts) == 2:
                user_id = int(parts[1])

                with file_lock:
                    with open(client, "r") as f:
                        lines = f.readlines()

                for line in lines:
                    fields = line.strip().split(",")
                    if int(fields[0]) == user_id:
                        usd = float(fields[6])
                        response = f"200 OK\nBalance: ${usd:.2f}\n"
                        conn.sendall(response.encode())
                        break
                else:
                    conn.sendall(b"400 invalid command\nUser not found\n")

            # LIST <user_id>
            elif cmd == "LIST" and len(parts) == 2:
                user_id = int(parts[1])

                with file_lock:
                    with open(stock, "r") as f:
                        lines = f.readlines()

                response = "200 OK\n"
                found = False
                for line in lines:
                    fields = line.strip().split(",")
                    if int(fields[4]) == user_id:
                        response += f"{fields[0]} {fields[1]} {fields[2]} {fields[3]} {fields[4]}\n"
                        found = True

                if not found:
                    response += "(none)\n"

                conn.sendall(response.encode())

            # BUY <symbol> <amount> <price> <user_id>
            elif cmd == "BUY" and len(parts) == 5:
                symbol = parts[1]
                amount = float(parts[2])
                price = float(parts[3])
                user_id = int(parts[4])

                cost = amount * price

                with file_lock:
                    with open(client, "r") as f:
                        user_lines = f.readlines()

                    updated_users = []
                    success = False

                    for line in user_lines:
                        if line.startswith("id,"):
                            updated_users.append(line)
                            continue

                        fields = line.strip().split(",")
                        if int(fields[0]) == user_id:
                            usd = float(fields[6])
                            if usd >= cost:
                                fields[6] = f"{usd - cost:.2f}"
                                success = True
                            updated_users.append(",".join(fields) + "\n")
                        else:
                            updated_users.append(line)

                    if not success:
                        conn.sendall(b"400 invalid command\nNot enough USD\n")
                        continue

                    with open(client, "w") as f:
                        f.writelines(updated_users)

                    with open(stock, "r") as f:
                        stock_lines = f.readlines()
                    stock_id = len(stock_lines)
                    with open(stock, "a") as f:
                        f.write(f"{stock_id},{symbol},N/A,{amount},{user_id}\n")

                conn.sendall(b"200 OK\nStock purchased\n")

            # SELL <symbol> <price> <amount> <user_id>
            elif cmd == "SELL" and len(parts) == 5:
                symbol = parts[1]
                price = float(parts[2])
                amount = float(parts[3])
                user_id = int(parts[4])

                with file_lock:
                    with open(stock, "r") as f:
                        stock_lines = f.readlines()

                    updated_stocks = []
                    sold = False

                    for line in stock_lines:
                        if line.startswith("id,"):
                            updated_stocks.append(line)
                            continue

                        fields = line.strip().split(",")
                        if int(fields[4]) == user_id and fields[1] == symbol:
                            current = float(fields[3])
                            if current >= amount:
                                fields[3] = f"{current - amount}"
                                sold = True
                            updated_stocks.append(",".join(fields) + "\n")
                        else:
                            updated_stocks.append(line)

                    if not sold:
                        conn.sendall(b"400 invalid command\nNot enough stock\n")
                        continue

                    with open(stock, "w") as f:
                        f.writelines(updated_stocks)

                    with open(client, "r") as f:
                        user_lines = f.readlines()

                    updated_users = []
                    for line in user_lines:
                        if line.startswith("id,"):
                            updated_users.append(line)
                            continue

                        fields = line.strip().split(",")
                        if int(fields[0]) == user_id:
                            usd = float(fields[6])
                            fields[6] = f"{usd + amount * price:.2f}"
                            updated_users.append(",".join(fields) + "\n")
                        else:
                            updated_users.append(line)

                    with open(client, "w") as f:
                        f.writelines(updated_users)

                conn.sendall(b"200 OK\nStock sold\n")

            # DEPOSIT <amount> (requires login)
            elif cmd == "DEPOSIT" and len(parts) == 2:
                if not logged_in:
                    conn.sendall(b"You are not logged in. Please log in first\n")
                    continue

                try:
                    amount = float(parts[1])
                except ValueError:
                    conn.sendall(b"400 invalid command\n")
                    continue

                if amount <= 0:
                    conn.sendall(b"400 invalid command\nDeposit amount must be positive\n")
                    continue

                user_id = current_user_id

                with file_lock:
                    with open(client, "r") as f:
                        user_lines = f.readlines()

                    updated_users = []
                    new_balance = 0.0

                    for line in user_lines:
                        fields = line.strip().split(",")
                        if int(fields[0]) == user_id:
                            usd = float(fields[6])
                            new_balance = usd + amount
                            fields[6] = f"{new_balance:.2f}"
                            updated_users.append(",".join(fields) + "\n")
                        else:
                            updated_users.append(line)

                    with open(client, "w") as f:
                        f.writelines(updated_users)

                response = f"200 OK\nDeposit successful. New balance ${new_balance:.2f}\n"
                conn.sendall(response.encode())

            # LOOKUP <ticker> (requires login)
            elif cmd == "LOOKUP" and len(parts) == 2:
                if not logged_in:
                    conn.sendall(b"403 Please login first\n")
                    continue

                ticker = parts[1].upper()
                user_id = current_user_id

                with file_lock:
                    with open(stock, "r") as f:
                        stock_lines = f.readlines()

                matches = []
                for line in stock_lines:
                    fields = line.strip().split(",")
                    stock_id = fields[0]
                    symbol = fields[1]
                    amount = fields[3]
                    owner_id = int(fields[4])

                    if owner_id == user_id and ticker in symbol.upper():
                        matches.append(f"{stock_id} {symbol} {amount}")

                if matches:
                    response = "200 OK\n"
                    response += f"Found {len(matches)} match"
                    if len(matches) != 1:
                        response += "es"
                    response += "\n"
                    response += "\n".join(matches) + "\n"
                else:
                    response = "404 Your search did not match any records.\n"

                conn.sendall(response.encode())

            # QUIT
            elif cmd == "QUIT":
                conn.sendall(b"200 OK\nClient quitting\n")
                break

            # SHUTDOWN (requires root)
            elif cmd == "SHUTDOWN":
                if not logged_in or current_user_id != 0:
                    conn.sendall(b"403 Please login as root to shutdown\n")
                    continue

                conn.sendall(b"200 OK\nServer shutting down\n")
                try:
                    if server_socket:
                        server_socket.close()
                except Exception:
                    pass
                os._exit(0)

            # invalid command
            else:
                conn.sendall(b"400 invalid command\n")

    finally:
        # Remove this session from active list (if logged in)
        if logged_in and current_user_id is not None:
            with active_sessions_lock:
                active_sessions[:] = [s for s in active_sessions if not (s[0] == current_user_id and s[2] == client_ip)]

        conn.close()
        print(f"Connection closed: {addr}")


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', SERVER_PORT))
    s.listen(MAX_PENDING)

    print(f"Server listening on port {SERVER_PORT}...")

    # Ensure users.txt exists and has at least 4 user accounts
    with file_lock:
        if not os.path.exists(client):
            open(client, "w").close()

        with open(client, "r") as f:
            lines = [line for line in f.readlines() if line.strip()]

        # If there are fewer than 4 users, append defaults until there are 4.
        if len(lines) < 4:
            print("Not enough users found. Adding default users.")
            defaults = [
                ("root@gmail.com", "Root", "LastName", "Root", "Root01", 100),
                ("mary@gmail.com", "Mary", "LastName", "Mary", "Mary01", 100),
                ("john@gmail.com", "John", "LastName", "John", "John01", 100),
                ("moe@gmail.com", "Moe", "LastName", "Moe", "Moe01", 100),
            ]

            with open(client, "a") as f:
                for i in range(len(lines), 4):
                    email, first_name, last_name, user_name, password, usd_balance = defaults[i]
                    f.write(f"{i},{email},{first_name},{last_name},{user_name},{password},{usd_balance}\n")

    #if stocks txt file empty, create new stock
    with open(stock, "r") as f:
        lines = f.readlines()
        if len(lines) <= 1:
            create_stock(
                stock_symbol="MCRO",
                stock_name="Microsoft",
                stock_balance=100,
                user_id=1
            )

    while True:
        try:
            conn, addr = s.accept()
        except OSError:
            # Socket was closed (e.g., from SHUTDOWN)
            break

        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    main()