import socket
import os

SERVER_PORT = 5432
MAX_PENDING = 5
MAX_LINE = 256

#define txt files
client = "users.txt"
stock = "stocks.txt"

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

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', SERVER_PORT))
    s.listen(MAX_PENDING)

    print(f"Server listening on port {SERVER_PORT}...")

    #if client txt file empty, create new default client
    with open(client, "r") as f:
        lines = f.readlines()
        if len(lines) <= 1:
            print("No users found. Creating first user.")
            create_user(
                email="example@gmail.com",
                first_name="First",
                last_name="User",
                user_name="user",
                password="pass123",
                usd_balance=100
            )

    #if stocks txt file empty, create new stock
    with open(stock, "r") as f:
        lines = f.readlines()
        if len(lines) <= 1:
            create_stock(
                stock_symbol="MCRO",
                stock_name="Microsoft",
                stock_balance=100,
                user_id=0
            )

    while True:
        new_s, addr = s.accept()
        print(f"Connected by {addr}")

        while True:
            data = new_s.recv(MAX_LINE)
            if not data:
                break

            #recieve message from client
            message = data.decode('utf-8').strip()
            print(message)

            parts = message.split()
            if not parts:
                new_s.sendall(b"400 invalid command\n")
                continue
# -------------------BALANCE----------------
            #if message recieved is BALANCE with correct details
            if parts[0] == "BALANCE" and len(parts) == 1:
                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                user_id = current_user_id
                #open client folder
                with open(client, "r") as f:
                    lines = f.readlines()

                #read balance
                for line in lines:
                    fields = line.strip().split(",")
                    if int(fields[0]) == user_id:
                        usd = float(fields[6])
                        response = f"200 OK\nBalance: ${usd:.2f}\n"
                        new_s.sendall(response.encode())
                        break
                else:
                    new_s.sendall(b"400 invalid command\nUser not found\n")
# -------------------LIST----------------
            #if message recieved is LIST with correct details
            elif parts[0] == "LIST" and len(parts) == 1:
                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                # read all users so we can map user_id -> username
                with open(client, "r") as f:
                    user_lines = f.readlines()

                user_map = {}
                for line in user_lines:
                    fields = line.strip().split(",")
                    user_map[int(fields[0])] = fields[4]   # username column

                # read all stock records
                with open(stock, "r") as f:
                    stock_lines = f.readlines()

                records = []

                # root sees all stock records
                if current_user.lower() == "root":
                    for line in stock_lines:
                        fields = line.strip().split(",")
                        stock_id = fields[0]
                        symbol = fields[1]
                        amount = fields[3]
                        owner_id = int(fields[4])

                        owner_name = user_map.get(owner_id, "unknown")
                        records.append(f"{stock_id} {symbol} {amount} {owner_name}")

                    response = "200 OK\nThe list of records in the Stock database:\n"
                    if records:
                        response += "\n".join(records) + "\n"
                    else:
                        response += "(none)\n"

                    new_s.sendall(response.encode())

                # normal user sees only their own stock records
                else:
                    for line in stock_lines:
                        fields = line.strip().split(",")
                        stock_id = fields[0]
                        symbol = fields[1]
                        amount = fields[3]
                        owner_id = int(fields[4])

                        if owner_id == current_user_id:
                            records.append(f"{stock_id} {symbol} {amount}")

                    response = f"200 OK\nThe list of records in the Stock database for {current_user}:\n"
                    if records:
                        response += "\n".join(records) + "\n"
                    else:
                        response += "(none)\n"

                    new_s.sendall(response.encode())
# -------------------BUY----------------
            #if message recieved is BUY with correct details
            elif parts[0] == "BUY" and len(parts) == 4:
                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                symbol = parts[1]

                try:
                    amount = float(parts[2])
                    price = float(parts[3])
                except ValueError:
                    new_s.sendall(b"400 invalid command\n")
                    continue

                if amount <= 0 or price <= 0:
                    new_s.sendall(b"400 invalid command\n")
                    continue

                user_id = current_user_id
                cost = amount * price

                with open(client, "r") as f:
                    user_lines = f.readlines()

                updated_users = []
                success = False
                found_user = False

                for line in user_lines:
                    fields = line.strip().split(",")

                    if int(fields[0]) == user_id:
                        found_user = True
                        usd = float(fields[6])

                        if usd >= cost:
                            fields[6] = f"{usd - cost:.2f}"
                            success = True

                        updated_users.append(",".join(fields) + "\n")
                    else:
                        updated_users.append(line)

                if not found_user:
                    new_s.sendall(b"400 invalid command\nUser not found\n")
                    continue

                if not success:
                    new_s.sendall(b"400 invalid command\nNot enough USD\n")
                    continue

                with open(client, "w") as f:
                    f.writelines(updated_users)

                with open(stock, "r") as f:
                    stock_lines = f.readlines()

                new_stock_id = len(stock_lines)

                with open(stock, "a") as f:
                    f.write(f"{new_stock_id},{symbol},N/A,{amount},{user_id}\n")

                new_s.sendall(b"200 OK\nStock purchased\n")
# -------------------SELL----------------
            #if message recieved is SELL with correct details
            elif parts[0] == "SELL" and len(parts) == 4:
                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                symbol = parts[1]

                try:
                    price = float(parts[2])
                    amount = float(parts[3])
                except ValueError:
                    new_s.sendall(b"400 invalid command\n")
                    continue

                if price <= 0 or amount <= 0:
                    new_s.sendall(b"400 invalid command\n")
                    continue

                user_id = current_user_id

                with open(stock, "r") as f:
                    stock_lines = f.readlines()

                updated_stocks = []
                sold = False

                for line in stock_lines:
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
                    new_s.sendall(b"400 invalid command\nNot enough stock\n")
                    continue

                with open(stock, "w") as f:
                    f.writelines(updated_stocks)

                with open(client, "r") as f:
                    user_lines = f.readlines()

                updated_users = []

                for line in user_lines:
                    fields = line.strip().split(",")

                    if int(fields[0]) == user_id:
                        usd = float(fields[6])
                        fields[6] = f"{usd + amount * price:.2f}"
                        updated_users.append(",".join(fields) + "\n")
                    else:
                        updated_users.append(line)

                with open(client, "w") as f:
                    f.writelines(updated_users)

                new_s.sendall(b"200 OK\nStock sold\n")
# -------------------DEPOSIT----------------
            elif parts[0] == "DEPOSIT" and len(parts) == 2:

                if not logged_in:
                    new_s.sendall(b"You are not logged in. Please log in first\n")
                    continue

                try:
                    amount = float(parts[1])
                except ValueError:
                    new_s.sendall(b"400 invalid command\n")
                    continue

                if amount <= 0:
                    new_s.sendall(b"400 invalid command\nDeposit amount must be positive\n")
                    continue

                user_id = current_user_id

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
                new_s.sendall(response.encode())
# -------------------LOOKUP----------------
            elif parts[0] == "LOOKUP" and len(parts) == 2:

                # user must be logged in
                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                ticker = parts[1].upper()
                user_id = current_user_id

                with open(stock, "r") as f:
                    stock_lines = f.readlines()

                matches = []

                for line in stock_lines:
                    fields = line.strip().split(",")

                    stock_id = fields[0]
                    symbol = fields[1]
                    amount = fields[3]
                    owner_id = int(fields[4])

                    # check ownership AND partial ticker match
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

                new_s.sendall(response.encode())
                    
# -------------------QUIT----------------
            #if message recieved is QUIT
            elif parts[0] == "QUIT":
                new_s.sendall(b"200 OK\nClient quitting\n")
                new_s.close()
                break
# -------------------SHUTDOWN----------------
            #if message recieved is SHUTDOWN
            #if message received is SHUTDOWN
            elif parts[0] == "SHUTDOWN" and len(parts) == 1:

                if not logged_in:
                    new_s.sendall(b"403 Please login first\n")
                    continue

                if current_user.lower() != "root":
                    new_s.sendall(b"403 Unauthorized action\n")
                    continue

                new_s.sendall(b"200 OK\nServer shutting down\n")

                new_s.close()
                s.close()
                return
            else:
                new_s.sendall(b"400 invalid command\n")
        new_s.close()
        print(f"Connection closed: {addr}")

if __name__ == "__main__":
    main()