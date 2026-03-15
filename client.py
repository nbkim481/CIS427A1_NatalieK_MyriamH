import socket
import sys

SERVER_PORT = 5432
MAX_LINE = 256
RECV_SIZE = 4096  

def main():
    if len(sys.argv) != 2:
        print("usage: simplex-talk host", file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error as e:
        print(f"simplex-talk: socket error: {e}", file=sys.stderr)
        sys.exit(1)

    # connect to server
    try:
        s.connect((host, SERVER_PORT))
    except socket.gaierror:
        print(f"simplex-talk: unknown host: {host}", file=sys.stderr)
        sys.exit(1)
    except socket.error as e:
        print(f"simplex-talk: connect error: {e}", file=sys.stderr)
        s.close()
        sys.exit(1)

    print("Successfully connected to server!!")
    print("Enter commands: BALANCE <id>, LIST <id>, BUY <sym> <amt> <price> <id>, SELL <sym> <price> <amt> <id>, QUIT, SHUTDOWN\n")

    try:
        for line in sys.stdin:
            line = line[:MAX_LINE - 1]

            if not line.endswith("\n"):
                line += "\n"

            # send to server
            try:
                s.sendall(line.encode("utf-8"))
            except socket.error as e:
                print(f"simplex-talk: send error: {e}", file=sys.stderr)
                break

            # receive server response 
            try:
                resp = s.recv(RECV_SIZE)
            except socket.error as e:
                print(f"simplex-talk: recv error: {e}", file=sys.stderr)
                break

            if not resp:
                print("Connection Closed")
                break

            print(resp.decode("utf-8", errors="replace"), end="")

            cmd = line.strip()
            if cmd == "QUIT" or cmd == "SHUTDOWN":
                break

    except KeyboardInterrupt:
        pass
    finally:
        s.close()

if __name__ == "__main__":
    main()
