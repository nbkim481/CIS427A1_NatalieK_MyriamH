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
                user_id=1
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

            #if message recieved is BALANCE with correct details
            if parts[0] == "BALANCE" and len(parts) == 2:
                user_id = int(parts[1])

                #open client folder
                with open(client, "r") as f:
                    lines = f.readlines()[1:]

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

            #if message recieved is LIST with correct details
            elif parts[0] == "LIST" and len(parts) == 2:
                user_id = int(parts[1])

                #open stock txt file
                with open(stock, "r") as f:
                    lines = f.readlines()[1:]

                response = "200 OK\n"
                found = False
                #return all stocks
                for line in lines:
                    fields = line.strip().split(",")
                    if int(fields[4]) == user_id:
                        response += f"{fields[0]} {fields[1]} {fields[2]} {fields[3]} {fields[4]}\n"
                        found = True

                #empty stocks txt file error
                if not found:
                    response += "(none)\n"

                new_s.sendall(response.encode())

            #if message recieved is BUY with correct details
            elif parts[0] == "BUY" and len(parts) == 5:
                symbol = parts[1]
                amount = float(parts[2])
                price = float(parts[3])
                user_id = int(parts[4])

                #calculate cost
                cost = amount * price

                #open client txt file
                with open(client, "r") as f:
                    user_lines = f.readlines()

                updated_users = []
                success = False
                
                #look for user
                for line in user_lines:
                    if line.startswith("id,"):
                        updated_users.append(line)
                        continue
                #find user balance
                    fields = line.strip().split(",")
                    if int(fields[0]) == user_id:
                        usd = float(fields[6])
                        if usd >= cost:
                            fields[6] = f"{usd - cost:.2f}"
                            success = True
                        updated_users.append(",".join(fields) + "\n")
                    else:
                        updated_users.append(line)

                #user does not have enough balance
                if not success:
                    new_s.sendall(b"400 invalid command\nNot enough USD\n")
                    continue

                with open(client, "w") as f:
                    f.writelines(updated_users)

                with open(stock, "a") as f:
                    f.write(f"{len(open(stock).readlines())},{symbol},N/A,{amount},{user_id}\n")

                new_s.sendall(b"200 OK\nStock purchased\n")

            #if message recieved is SELL with correct details
            elif parts[0] == "SELL" and len(parts) == 5:
                symbol = parts[1]
                price = float(parts[2])
                amount = float(parts[3])
                user_id = int(parts[4])

                #open stock txt file
                with open(stock, "r") as f:
                    stock_lines = f.readlines()

                updated_stocks = []
                sold = False

                #look for stock user want to sell
                for line in stock_lines:
                    if line.startswith("id,"):
                        updated_stocks.append(line)
                        continue

                    #sell and update stocks
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

                new_s.sendall(b"200 OK\nStock sold\n")

            #if message recieved is QUIT
            elif parts[0] == "QUIT":
                new_s.sendall(b"200 OK\nClient quitting\n")
                break

            #if message recieved is SHUTDOWN
            elif parts[0] == "SHUTDOWN":
                new_s.sendall(b"200 OK\nServer shutting down\n")
                new_s.close()
                s.close()
                return

            #if message recieved is invalid
            else:
                new_s.sendall(b"400 invalid command\n")

        new_s.close()
        print(f"Connection closed: {addr}")


if __name__ == "__main__":
    main()